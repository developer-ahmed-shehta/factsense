"""
Automated Test Suite for Batch 6: Production Planning, Work Orders & ERP Sync (F18).
Verifies:
1. Complete work order lifecycle (DRAFT -> PLANNED -> RELEASED -> IN_PROGRESS -> COMPLETED / SHORT_CLOSED).
2. Process routing stage sequencing and progress tracking.
3. Component BOM material staging and shortage alerts.
4. Visual machine x shift allocation calendar matrix.
5. Inbound ERP / Odoo synchronization, idempotency, conflict detection, and resolution.
6. Sync run retry mechanism and outbound feedback export.
7. Strict role-based authorization (RBAC) and zero-emoji compliance.
"""

import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Process, Product, Shift
from apps.planning.models import (
    WorkOrder, WorkOrderRoutingStage, MachineShiftAssignment,
    WorkOrderMaterial, MaterialDelivery, ERPSyncRun, ERPSyncConflict
)
from apps.planning.services import work_order_service, erp_service

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u24C2]"
)


class PlanningBaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Factory & Line
        self.factory = Factory.objects.create(code='FAC-TEST', name='Test Factory')
        self.line = Line.objects.create(
            factory=self.factory,
            code='LINE-TEST-01',
            name='Test Packaging Line'
        )

        # Bottleneck Machine
        self.machine = Machine.objects.create(
            line=self.line,
            code='FL-30-TEST',
            name='Test Rotary Filler',
            category='FILLER',
            ideal_run_rate_cpm=120.0,
            sequence_order=3,
            is_bottleneck=True
        )
        self.line.bottleneck_machine = self.machine
        self.line.save()

        # Shifts
        self.shift_morning = Shift.objects.create(
            factory=self.factory,
            code='SHIFT-M',
            name='Morning Shift',
            start_time=time(7, 0),
            end_time=time(15, 0),
            sequence=1
        )
        self.shift_evening = Shift.objects.create(
            factory=self.factory,
            code='SHIFT-E',
            name='Evening Shift',
            start_time=time(15, 0),
            end_time=time(23, 0),
            sequence=2
        )

        # Product & Processes
        self.proc_blow = Process.objects.create(code='BLOW', name='Blow Molding', sequence_order=1)
        self.proc_fill = Process.objects.create(code='FILL', name='Filling & Capping', sequence_order=2)
        self.proc_pack = Process.objects.create(code='PACK', name='Case Packing', sequence_order=3)

        self.product = Product.objects.create(
            factory=self.factory,
            code='PRD-WTR-500ML',
            name='Pure Mineral Water 500ml',
            rated_speed_cpm=120,
            nominal_weight=Decimal('500.00'),
            unit_cost=Decimal('1.50'),
            scrap_cost=Decimal('0.80')
        )
        self.product.processes.add(self.proc_blow, self.proc_fill, self.proc_pack)

        # Roles
        self.planner_role, _ = Role.objects.get_or_create(code='planner', defaults={'name': 'Planner'})
        self.supply_chain_role, _ = Role.objects.get_or_create(code='supply_chain', defaults={'name': 'Supply Chain'})
        self.operator_role, _ = Role.objects.get_or_create(code='operator', defaults={'name': 'Operator'})

        # Users
        self.planner_user = User.objects.create_user(username='test_planner', password='password123')
        UserRoleAssignment.objects.create(user=self.planner_user, role=self.planner_role, is_active=True)

        self.supply_chain_user = User.objects.create_user(username='test_sc', password='password123')
        UserRoleAssignment.objects.create(user=self.supply_chain_user, role=self.supply_chain_role, is_active=True)

        self.operator_user = User.objects.create_user(username='test_op', password='password123')
        UserRoleAssignment.objects.create(user=self.operator_user, role=self.operator_role, is_active=True)

    def _login(self, user, role_code):
        self.client.login(username=user.username, password='password123')
        s = self.client.session
        s['active_role'] = role_code
        s.save()


class WorkOrderLifecycleTestCase(PlanningBaseTestCase):
    def test_work_order_creation_with_stages_and_bom(self):
        """Verify work order creation automatically initializes routing stages and BOM materials."""
        now = timezone.now()
        wo = work_order_service.create_work_order(
            order_number='WO-TEST-100',
            product_id=self.product.id,
            line_id=self.line.id,
            target_quantity=10000,
            planned_start=now,
            planned_end=now + timedelta(hours=8),
            priority='HIGH',
            created_by=self.planner_user
        )

        self.assertEqual(wo.status, 'PLANNED')
        self.assertEqual(wo.target_quantity, 10000)
        self.assertEqual(wo.produced_quantity, 0)
        self.assertEqual(wo.progress_percent, 0.0)
        self.assertEqual(wo.remaining_quantity, 10000)

        # Stages verification
        stages = wo.stages.all().order_by('sequence_order')
        self.assertEqual(stages.count(), 3)
        self.assertEqual(stages[0].process.code, 'BLOW')
        self.assertEqual(stages[1].process.code, 'FILL')
        self.assertEqual(stages[2].process.code, 'PACK')

        # BOM materials verification
        materials = wo.materials.all()
        self.assertEqual(materials.count(), 4)
        preform = materials.filter(material_code__icontains='PREFORM').first()
        self.assertIsNotNone(preform)
        self.assertEqual(preform.required_quantity, Decimal('10000.0'))
        self.assertEqual(preform.status, 'PENDING')

    def test_full_lifecycle_release_start_complete(self):
        """Verify normal happy-path lifecycle: PLANNED -> RELEASED -> IN_PROGRESS -> COMPLETED."""
        now = timezone.now()
        wo = work_order_service.create_work_order(
            order_number='WO-TEST-101',
            product_id=self.product.id,
            line_id=self.line.id,
            target_quantity=5000,
            planned_start=now,
            planned_end=now + timedelta(hours=4),
            created_by=self.planner_user
        )

        # 1. Release
        self.assertTrue(wo.can_release)
        work_order_service.release_work_order(wo, user=self.planner_user)
        self.assertEqual(wo.status, 'RELEASED')

        # 2. Start
        self.assertTrue(wo.can_start)
        work_order_service.start_work_order(wo, user=self.planner_user)
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertIsNotNone(wo.actual_start)
        self.line.refresh_from_db()
        self.assertEqual(self.line.current_product, self.product)
        first_stage = wo.stages.first()
        self.assertEqual(first_stage.status, 'IN_PROGRESS')

        # 3. Stage progress advancement
        work_order_service.record_stage_progress(first_stage, completed_units=5000, scrap_units=50)
        first_stage.refresh_from_db()
        self.assertEqual(first_stage.status, 'COMPLETED')
        self.assertEqual(first_stage.completed_quantity, 5000)

        # Next stage should auto-activate
        second_stage = wo.stages.filter(sequence_order=2).first()
        self.assertEqual(second_stage.status, 'IN_PROGRESS')

        # Complete final stage
        third_stage = wo.stages.filter(sequence_order=3).first()
        work_order_service.record_stage_progress(third_stage, completed_units=5000, scrap_units=20)
        wo.refresh_from_db()
        self.assertEqual(wo.produced_quantity, 5000)

        # 4. Complete
        self.assertTrue(wo.can_complete)
        work_order_service.complete_work_order(wo, user=self.planner_user)
        self.assertEqual(wo.status, 'COMPLETED')
        self.assertIsNotNone(wo.actual_end)

    def test_pause_resume_lifecycle(self):
        """Verify IN_PROGRESS -> PAUSED -> IN_PROGRESS transitions."""
        now = timezone.now()
        wo = work_order_service.create_work_order(
            order_number='WO-TEST-102',
            product_id=self.product.id,
            line_id=self.line.id,
            target_quantity=2000,
            planned_start=now,
            planned_end=now + timedelta(hours=2)
        )
        work_order_service.release_work_order(wo)
        work_order_service.start_work_order(wo)

        # Pause
        self.assertTrue(wo.can_pause)
        work_order_service.pause_work_order(wo)
        self.assertEqual(wo.status, 'PAUSED')

        # Resume
        self.assertTrue(wo.can_resume)
        work_order_service.resume_work_order(wo)
        self.assertEqual(wo.status, 'IN_PROGRESS')

    def test_short_close_requires_mandatory_justification(self):
        """Verify short-close requires non-empty justification reason and archives order."""
        now = timezone.now()
        wo = work_order_service.create_work_order(
            order_number='WO-TEST-103',
            product_id=self.product.id,
            line_id=self.line.id,
            target_quantity=8000,
            planned_start=now,
            planned_end=now + timedelta(hours=6)
        )
        work_order_service.release_work_order(wo)

        # Empty reason rejected
        with self.assertRaises(ValueError):
            work_order_service.short_close_work_order(wo, reason="")

        # Valid reason accepted
        work_order_service.short_close_work_order(wo, reason="Severe packaging material defect batch from supplier")
        self.assertEqual(wo.status, 'SHORT_CLOSED')
        self.assertIn("packaging material defect", wo.short_close_reason)
        self.assertIsNotNone(wo.actual_end)


class MaterialStagingTestCase(PlanningBaseTestCase):
    def test_material_staging_increments_and_shortage_alert(self):
        """Verify material staging percentage calculation, lot assignment, and shortage flagging."""
        now = timezone.now()
        wo = work_order_service.create_work_order(
            order_number='WO-MAT-01',
            product_id=self.product.id,
            line_id=self.line.id,
            target_quantity=10000,
            planned_start=now,
            planned_end=now + timedelta(hours=8)
        )
        mat = wo.materials.filter(material_code__icontains='PREFORM').first()
        self.assertEqual(mat.status, 'PENDING')
        self.assertEqual(mat.staged_quantity, Decimal('0.0'))

        # Partial stage 50%
        work_order_service.stage_material(mat, staged_qty=5000, lot_number='LOT-PRE-901', user=self.planner_user)
        mat.refresh_from_db()
        self.assertEqual(mat.status, 'PARTIALLY_STAGED')
        self.assertEqual(mat.staged_quantity, Decimal('5000.0'))
        self.assertEqual(mat.staged_percent, 50.0)
        self.assertFalse(mat.is_fully_staged)

        # Complete staging 100%
        work_order_service.stage_material(mat, staged_qty=5000, lot_number='LOT-PRE-902', user=self.planner_user)
        mat.refresh_from_db()
        self.assertEqual(mat.status, 'STAGED')
        self.assertEqual(mat.staged_percent, 100.0)
        self.assertTrue(mat.is_fully_staged)

        # Flag shortage on caps
        cap_mat = wo.materials.filter(material_code__icontains='CAP').first()
        work_order_service.flag_material_shortage(cap_mat, shortage_notes='Warehouse stock depleted', user=self.planner_user)
        cap_mat.refresh_from_db()
        self.assertEqual(cap_mat.status, 'SHORTAGE')
        self.assertEqual(cap_mat.shortage_notes, 'Warehouse stock depleted')


class ShiftScheduleMatrixTestCase(PlanningBaseTestCase):
    def test_assign_work_order_to_shift_matrix(self):
        """Verify allocating work order to shift calendar slot creates MachineShiftAssignment."""
        now = timezone.now()
        today = now.date()
        wo = work_order_service.create_work_order(
            order_number='WO-SCHED-01',
            product_id=self.product.id,
            line_id=self.line.id,
            target_quantity=12000,
            planned_start=now,
            planned_end=now + timedelta(hours=12)
        )

        assignment = work_order_service.assign_shift_schedule(
            work_order=wo,
            shift=self.shift_morning,
            scheduled_date=today,
            target_units=6000,
            machine=self.machine,
            notes='Primary bottling run',
            user=self.planner_user
        )
        self.assertEqual(assignment.status, 'SCHEDULED')
        self.assertEqual(assignment.planned_target_units, 6000)
        self.assertEqual(assignment.machine, self.machine)
        self.assertEqual(assignment.shift, self.shift_morning)


class ERPSyncAndConflictTestCase(PlanningBaseTestCase):
    def test_inbound_erp_sync_idempotency_and_creation(self):
        """Verify inbound ERP pull idempotently ingests work orders without duplicates."""
        # 1. First Sync Run
        sync_run1 = erp_service.simulate_erp_pull(user=self.planner_user)
        self.assertEqual(sync_run1.status, 'SUCCESS')
        self.assertGreater(sync_run1.records_created, 0)
        self.assertEqual(sync_run1.records_conflicted, 0)

        initial_count = WorkOrder.objects.count()
        self.assertGreater(initial_count, 0)

        # 2. Second Sync Run (Idempotent: 0 created, 0 conflicts)
        sync_run2 = erp_service.simulate_erp_pull(user=self.planner_user)
        self.assertEqual(sync_run2.status, 'SUCCESS')
        self.assertEqual(sync_run2.records_created, 0)
        self.assertEqual(WorkOrder.objects.count(), initial_count)

    def test_inbound_conflict_detection_and_resolution(self):
        """Verify conflict detected on active floor order, logged in conflict queue, and resolved."""
        # 1. Ingest an order and transition it to IN_PROGRESS on floor
        sync_run = erp_service.simulate_erp_pull(user=self.planner_user)
        wo = WorkOrder.objects.filter(external_erp_id='ODOO-MO-8941').first()
        self.assertIsNotNone(wo)
        work_order_service.release_work_order(wo)
        work_order_service.start_work_order(wo)
        self.assertEqual(wo.status, 'IN_PROGRESS')

        # 2. Run sync with force_conflict=True simulating ERP modifying target quantity upstream
        conflict_run = erp_service.simulate_erp_pull(user=self.planner_user, force_conflict=True)
        self.assertEqual(conflict_run.status, 'PARTIAL')
        self.assertGreater(conflict_run.records_conflicted, 0)

        conflict = ERPSyncConflict.objects.filter(sync_run=conflict_run, external_erp_id='ODOO-MO-8941').first()
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.conflict_type, 'QUANTITY_DISCREPANCY')
        self.assertEqual(conflict.resolution, 'UNRESOLVED')

        # 3. Resolve conflict by accepting remote ERP value
        erp_service.resolve_erp_conflict(conflict, resolution_choice='ACCEPTED_REMOTE', user=self.planner_user)
        conflict.refresh_from_db()
        self.assertEqual(conflict.resolution, 'ACCEPTED_REMOTE')
        wo.refresh_from_db()
        self.assertEqual(wo.target_quantity, int(conflict.remote_value))

        # 4. Verify parent sync_run auto-updates to SUCCESS once all conflicts resolved
        conflict_run.refresh_from_db()
        self.assertEqual(conflict_run.status, 'SUCCESS')

    def test_outbound_feedback_export_and_retry(self):
        """Verify exporting completed feedback to ERP and retrying sync runs."""
        wo = WorkOrder.objects.create(
            order_number='WO-EXP-01',
            external_erp_id='ODOO-MO-9999',
            product=self.product,
            line=self.line,
            target_quantity=5000,
            produced_quantity=4980,
            scrap_quantity=20,
            status='COMPLETED',
            planned_start=timezone.now(),
            planned_end=timezone.now()
        )
        export_run = erp_service.simulate_erp_push_feedback(wo, user=self.planner_user)
        self.assertEqual(export_run.direction, 'OUTBOUND_EXPORT')
        self.assertEqual(export_run.status, 'SUCCESS')
        self.assertIn('Produced: 4980', export_run.log_summary)

        # Retry
        erp_service.retry_sync_run(export_run, user=self.planner_user)
        export_run.refresh_from_db()
        self.assertEqual(export_run.retry_count, 1)


class PlanningViewsAndRBACTestCase(PlanningBaseTestCase):
    def test_planner_and_supply_chain_views_render_200(self):
        """Verify all planning & work order views render successfully with zero emojis."""
        self._login(self.supply_chain_user, 'supply_chain')

        urls = [
            '/work-orders/',
            '/work-orders/schedule/',
            '/work-orders/materials/',
            '/work-orders/erp-sync/',
        ]
        for u in urls:
            resp = self.client.get(u)
            self.assertEqual(resp.status_code, 200, f"URL {u} returned non-200 status {resp.status_code}")
            content = resp.content.decode('utf-8')
            self.assertFalse(bool(EMOJI_PATTERN.search(content)), f"Found emoji in URL {u}!")

    def test_operator_blocked_from_work_order_management_actions(self):
        """Verify Line Operator receives HTTP 403 Forbidden when attempting planning mutations."""
        self._login(self.operator_user, 'operator')

        # Cannot access ERP Sync
        resp_sync = self.client.get('/work-orders/erp-sync/')
        self.assertEqual(resp_sync.status_code, 403)

        # Cannot create work order
        resp_create = self.client.post('/work-orders/create/', {
            'order_number': 'WO-HACK',
            'product_id': str(self.product.id),
            'line_id': str(self.line.id),
            'target_quantity': '500'
        })
        self.assertEqual(resp_create.status_code, 403)
