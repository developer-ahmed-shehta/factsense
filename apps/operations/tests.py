"""
Automated Test Suite for FactSense Shop-Floor Operations, Maintenance & Handovers.
Strictly verifies Batch 4 acceptance criteria:
- F05: Operator Touch Console (Touch targets, counters, classification, split, scrap numpad, scale weight, maintenance call)
- F06: Stoppages Intelligence, Juran 80/20 Pareto & Digital SMED 4-Phase Stopwatch
- F15: Live Floor Matrix & Guided 3-Step Shift Handover
- F16: Maintenance 5-Stage Kanban, Repair Clock-in, Spares SLA Pausing & Mandatory Root Cause Release
- Gate Before Completion: "Complete operator breakdown-to-release journey; shift handover closes cleanly."
- Zero Emojis Compliance across all templates.
"""

import json
import re
from datetime import time, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import (
    Factory, Line, Machine, Shift, PlannedBreak, Product,
    ReasonCategory, StoppageReason, DefectReason
)
from apps.telemetry.models import MachineCurrentState, DowntimeEvent
from apps.operations.models import (
    MaintenanceTicket, SparePart, SparePartRequisition, ChangeoverEvent,
    DefectLog, WeightSample, ShiftHandover
)
from apps.operations.services.stoppage_service import (
    classify_stoppage_event, split_stoppage_event, calculate_juran_pareto, calculate_reliability_metrics
)
from apps.operations.services.maintenance_service import (
    is_machine_locked_by_maintenance, create_operator_maintenance_call,
    cancel_operator_maintenance_call, technician_clock_in, request_spare_part_for_ticket,
    deliver_spare_part_and_resume, resolve_and_release_machine
)
from apps.operations.services.smed_service import start_smed_changeover, advance_smed_phase
from apps.operations.services.shift_service import get_or_create_shift_handover, submit_and_lock_shift_handover

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u24C2]"
)


class OperationsBaseTestCase(TestCase):
    """Base setup for Batch 4 operations tests."""

    def setUp(self):
        self.client = Client()

        # Seed roles
        self.operator_role, _ = Role.objects.get_or_create(
            code='operator', defaults={'name': 'Operator', 'default_landing': '/operator/'}
        )
        self.supervisor_role, _ = Role.objects.get_or_create(
            code='supervisor', defaults={'name': 'Supervisor', 'default_landing': '/floor/'}
        )
        self.maintenance_role, _ = Role.objects.get_or_create(
            code='maintenance', defaults={'name': 'Maintenance', 'default_landing': '/maintenance/'}
        )
        self.admin_role, _ = Role.objects.get_or_create(
            code='admin', defaults={'name': 'Admin', 'default_landing': '/administration/'}
        )

        # Seed users
        self.operator_user = User.objects.create_user(
            username='test_operator', password='Factsense@2026', first_name='Operator', last_name='One'
        )
        UserRoleAssignment.objects.create(user=self.operator_user, role=self.operator_role, is_active=True)

        self.supervisor_user = User.objects.create_user(
            username='test_supervisor', password='Factsense@2026', first_name='Shift', last_name='Supervisor'
        )
        UserRoleAssignment.objects.create(user=self.supervisor_user, role=self.supervisor_role, is_active=True)

        self.maintenance_user = User.objects.create_user(
            username='test_tech', password='Factsense@2026', first_name='Tariq', last_name='Technician'
        )
        UserRoleAssignment.objects.create(user=self.maintenance_user, role=self.maintenance_role, is_active=True)

        self.admin_user = User.objects.create_user(
            username='test_admin', password='Factsense@2026', first_name='Admin', last_name='User'
        )
        UserRoleAssignment.objects.create(user=self.admin_user, role=self.admin_role, is_active=True)

        # Factory & Line setup
        self.factory = Factory.objects.create(
            code='FAC-OPS', name='Operations Plant', currency='EGP'
        )
        self.product_a = Product.objects.create(
            factory=self.factory, code='SKU-BOT-500', name='Water 500ml',
            nominal_weight=Decimal('500.00'), usl_weight=Decimal('505.00'), lsl_weight=Decimal('495.00')
        )
        self.product_b = Product.objects.create(
            factory=self.factory, code='SKU-BOT-1500', name='Water 1500ml',
            nominal_weight=Decimal('1500.00'), usl_weight=Decimal('1510.00'), lsl_weight=Decimal('1490.00')
        )

        self.line = Line.objects.create(
            factory=self.factory, code='LINE-OPS-1', name='Packaging Line 1',
            current_product=self.product_a
        )

        self.machine_capper = Machine.objects.create(
            line=self.line, code='CP-01', name='Rotary Capper',
            category='CAPPER', sequence_order=20, ideal_run_rate_cpm=120.0, is_bottleneck=True
        )
        self.line.bottleneck_machine = self.machine_capper
        self.line.save()

        # Shift setup
        self.shift = Shift.objects.create(
            factory=self.factory, code='SHIFT-M', name='Morning Shift',
            start_time=time(7, 0), end_time=time(15, 0), unpaid_break_minutes=30, sequence=1
        )

        # Taxonomies
        self.cat_mech = ReasonCategory.objects.create(
            name='Mechanical Jam', department='MECHANICAL'
        )
        self.reason_cap_jam = StoppageReason.objects.create(
            category=self.cat_mech, code='CAP_JAM', name='Cap Chute Conveyor Jam',
            tpm_loss_type='AVAILABILITY_BREAKDOWN', is_planned=False
        )
        self.reason_waiting_parts = StoppageReason.objects.create(
            category=self.cat_mech, code='WAIT_SPARES', name='Waiting for Spare Parts Delivery',
            tpm_loss_type='AVAILABILITY_BREAKDOWN', is_planned=False
        )

        self.defect_underfill = DefectReason.objects.create(
            code='DEF-UND', name='Underfill Low Volume', category='VOLUME', default_disposition='SCRAP'
        )

        # Spare Part
        self.spare_spring = SparePart.objects.create(
            factory=self.factory, part_number='SP-CHK-01', name='Capping Chuck Spring',
            category='MECHANICAL', in_stock_quantity=10, min_stock_level=2, unit_cost=Decimal('75.00')
        )


class OperatorConsoleTestCase(OperationsBaseTestCase):
    """Tests for Operator Touch Console (F05) features and actions."""

    def test_operator_console_view_loads_for_operator(self):
        self.client.force_login(self.operator_user)
        response = self.client.get(reverse('operator_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rotary Capper')
        self.assertContains(response, 'GOOD PIECES ACCEPTED')

    def test_operator_increment_action(self):
        self.client.force_login(self.operator_user)
        url = reverse('operator_increment_action')
        response = self.client.post(url, {
            'machine_id': self.machine_capper.id,
            'increment': 5
        })
        self.assertEqual(response.status_code, 302)
        curr = self.machine_capper.current_state
        self.assertEqual(curr.shift_pulse_count, 5)
        self.assertEqual(curr.shift_good_count, 5)

    def test_operator_classify_stoppage_action(self):
        # Create unassigned downtime event
        event = DowntimeEvent.objects.create(
            machine=self.machine_capper,
            line=self.line,
            state_code='UNPLANNED_DOWNTIME',
            start_time=timezone.now() - timedelta(minutes=15),
            duration_seconds=900,
            tpm_loss_type='AVAILABILITY_BREAKDOWN',
            is_simulated=False
        )

        self.client.force_login(self.operator_user)
        url = reverse('operator_classify_action')
        response = self.client.post(url, {
            'event_id': event.id,
            'category_id': self.cat_mech.id,
            'reason_id': self.reason_cap_jam.id,
            'notes': 'Cleared jammed bottle caps in infeed chute.'
        })
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.category, self.cat_mech)
        self.assertEqual(event.reason, self.reason_cap_jam)
        self.assertEqual(event.category.department, 'MECHANICAL')
        self.assertEqual(event.classified_by, self.operator_user)

    def test_operator_split_stoppage_action(self):
        # Create a 30-minute stop (1800s)
        now = timezone.now()
        event = DowntimeEvent.objects.create(
            machine=self.machine_capper,
            line=self.line,
            state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=30),
            end_time=now,
            duration_seconds=1800,
            tpm_loss_type='AVAILABILITY_BREAKDOWN',
            is_simulated=False
        )

        self.client.force_login(self.operator_user)
        url = reverse('operator_split_action')
        # Split: 600s (10m) Mechanical Jam + 1200s (20m) Waiting for Parts
        response = self.client.post(url, {
            'event_id': event.id,
            'split_seconds': 600,
            'reason_id_1': self.reason_cap_jam.id,
            'reason_id_2': self.reason_waiting_parts.id,
            'notes_1': 'Physical jam',
            'notes_2': 'Waiting tech with spring'
        })
        self.assertEqual(response.status_code, 302)

        event.refresh_from_db()
        self.assertEqual(event.duration_seconds, 600)
        self.assertEqual(event.reason, self.reason_cap_jam)

        part2 = DowntimeEvent.objects.filter(machine=self.machine_capper).exclude(id=event.id).latest('start_time')
        self.assertEqual(part2.duration_seconds, 1200)
        self.assertEqual(part2.reason, self.reason_waiting_parts)
        self.assertEqual(event.end_time, part2.start_time)  # Non-overlapping boundary

    def test_operator_scrap_numpad_action(self):
        self.client.force_login(self.operator_user)
        url = reverse('operator_scrap_action')
        response = self.client.post(url, {
            'machine_id': self.machine_capper.id,
            'reason_id': self.defect_underfill.id,
            'quantity': 7,
            'disposition': 'SCRAP',
            'notes': 'Underfilled bottles at startup'
        })
        self.assertEqual(response.status_code, 302)

        defect = DefectLog.objects.filter(machine=self.machine_capper).latest('timestamp')
        self.assertEqual(defect.quantity, 7)
        self.assertEqual(defect.reason, self.defect_underfill)
        self.assertEqual(self.machine_capper.current_state.shift_scrap_count, 7)

    def test_operator_scale_weight_action(self):
        self.client.force_login(self.operator_user)
        url = reverse('operator_weight_action')
        response = self.client.post(url, {
            'machine_id': self.machine_capper.id,
            'measured_weight_grams': '501.20'
        })
        self.assertEqual(response.status_code, 302)

        sample = WeightSample.objects.filter(machine=self.machine_capper).latest('timestamp')
        self.assertEqual(sample.measured_weight_grams, Decimal('501.20'))
        self.assertAlmostEqual(float(sample.deviation_grams), 1.20, places=2)
        self.assertTrue(sample.is_within_spec)

    def test_operator_maintenance_call_and_cancel_lifecycle(self):
        self.client.force_login(self.operator_user)

        # 1. Operator calls maintenance
        call_url = reverse('operator_call_maintenance_action')
        res_call = self.client.post(call_url, {
            'machine_id': self.machine_capper.id,
            'description': 'Loud grinding sound in capper head.'
        })
        self.assertEqual(res_call.status_code, 302)

        ticket = MaintenanceTicket.objects.filter(machine=self.machine_capper, status='OPEN').first()
        self.assertIsNotNone(ticket)
        self.assertTrue(ticket.force_lockout)
        self.assertTrue(is_machine_locked_by_maintenance(self.machine_capper))
        self.assertEqual(self.machine_capper.current_state.state_code, 'UNPLANNED_DOWNTIME')

        # 2. When locked, piece increments are blocked
        inc_res = self.client.post(reverse('operator_increment_action'), {
            'machine_id': self.machine_capper.id,
            'increment': 1
        })
        self.assertEqual(inc_res.status_code, 302)
        self.assertEqual(self.machine_capper.current_state.shift_pulse_count, 0)

        # 3. Operator cancels unassigned call (cleared minor jam)
        cancel_url = reverse('operator_cancel_call_action')
        res_cancel = self.client.post(cancel_url, {'ticket_id': ticket.id})
        self.assertEqual(res_cancel.status_code, 302)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'CLOSED')
        self.assertFalse(is_machine_locked_by_maintenance(self.machine_capper))


class MaintenanceKanbanTestCase(OperationsBaseTestCase):
    """
    Tests 5-Stage Kanban Incident Board, technician repair clock-in,
    spare parts SLA pausing, and machine release back to production (F16).
    """

    def test_complete_breakdown_to_release_journey(self):
        """
        Gate Requirement Verification:
        Complete operator breakdown-to-release journey:
        1. Breakdown occurs & operator calls technician -> Lockout engages.
        2. Technician clocks in -> Ticket moves to IN_PROGRESS.
        3. Technician requests spare part -> WAITING_SPARES (SLA paused).
        4. Warehouse delivers spare -> IN_PROGRESS resumes.
        5. Mandatory root cause & solution recorded -> Machine released and unlocked!
        """
        # Step 1: Breakdown call from operator
        ticket = create_operator_maintenance_call(self.machine_capper, self.operator_user, "Motor tripped")
        self.assertTrue(is_machine_locked_by_maintenance(self.machine_capper))
        self.assertEqual(ticket.status, 'OPEN')

        # Step 2: Technician clocks in
        technician_clock_in(ticket.id, self.maintenance_user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'IN_PROGRESS')
        self.assertEqual(ticket.assigned_to, self.maintenance_user)
        self.assertIsNotNone(ticket.work_started_at)

        # Step 3: Technician requests spare part (pauses SLA)
        req = request_spare_part_for_ticket(ticket.id, self.spare_spring.id, quantity=1, user=self.maintenance_user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'WAITING_SPARES')
        self.assertIsNotNone(ticket.waiting_spares_started_at)

        # Step 4: Warehouse delivers spare part
        deliver_spare_part_and_resume(req.id, self.admin_user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'IN_PROGRESS')
        self.spare_spring.refresh_from_db()
        self.assertEqual(self.spare_spring.in_stock_quantity, 9)  # 10 - 1
        self.assertIsNone(ticket.waiting_spares_started_at)

        # Step 5: Resolve and release machine back to production
        resolve_and_release_machine(
            ticket_id=ticket.id,
            root_cause_notes="Fatigue failure of chuck spring after extensive run.",
            solution_notes="Replaced spring with SP-CHK-01 and calibrated torque to 2.4 Nm.",
            root_cause_category_id=self.cat_mech.id,
            root_cause_reason_id=self.reason_cap_jam.id,
            parts_used="1x SP-CHK-01",
            technician_user=self.maintenance_user
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'RESOLVED')
        self.assertFalse(ticket.force_lockout)

        # Machine is unlocked and returned to RUNNING
        self.assertFalse(is_machine_locked_by_maintenance(self.machine_capper))
        self.machine_capper.refresh_from_db()
        self.assertEqual(self.machine_capper.current_state.state_code, 'RUNNING')

    def test_resolve_requires_mandatory_notes(self):
        ticket = create_operator_maintenance_call(self.machine_capper, self.operator_user)
        with self.assertRaises(ValueError):
            resolve_and_release_machine(ticket.id, root_cause_notes="", solution_notes="")


class StoppagesAndReliabilityTestCase(OperationsBaseTestCase):
    """Tests Juran 80/20 Pareto distribution and reliability engineering KPIs (F06)."""

    def test_juran_pareto_calculation(self):
        now = timezone.now()
        # Create 3 stoppage events: 60 min cap jam, 30 min cap jam, 10 min waiting parts
        DowntimeEvent.objects.create(
            machine=self.machine_capper, line=self.line, state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=100), duration_seconds=3600,
            reason=self.reason_cap_jam, category=self.cat_mech, is_planned=False
        )
        DowntimeEvent.objects.create(
            machine=self.machine_capper, line=self.line, state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=40), duration_seconds=1800,
            reason=self.reason_cap_jam, category=self.cat_mech, is_planned=False
        )
        DowntimeEvent.objects.create(
            machine=self.machine_capper, line=self.line, state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=10), duration_seconds=600,
            reason=self.reason_waiting_parts, category=self.cat_mech, is_planned=False
        )

        pareto = calculate_juran_pareto(line=self.line, days=7)
        self.assertEqual(pareto['total_downtime_minutes'], 100.0)
        self.assertEqual(pareto['total_stoppage_count'], 3)

        # Top cause by duration is Cap Chute Jam (90 min = 90%)
        top_duration = pareto['by_duration'][0]
        self.assertEqual(top_duration['label'], 'Cap Chute Conveyor Jam')
        self.assertEqual(top_duration['minutes'], 90.0)
        self.assertEqual(top_duration['cum_pct'], 90.0)

    def test_reliability_metrics_calculation(self):
        now = timezone.now()
        # 2 breakdowns: 30 min + 15 min = 45 min total downtime
        DowntimeEvent.objects.create(
            machine=self.machine_capper, line=self.line, state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=60), duration_seconds=1800,
            tpm_loss_type='AVAILABILITY_BREAKDOWN', is_planned=False
        )
        DowntimeEvent.objects.create(
            machine=self.machine_capper, line=self.line, state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=20), duration_seconds=900,
            tpm_loss_type='AVAILABILITY_BREAKDOWN', is_planned=False
        )

        # 1-day baseline (450 min planned)
        metrics = calculate_reliability_metrics(line=self.line, days=1)
        self.assertEqual(metrics['breakdown_count'], 2)
        self.assertEqual(metrics['total_breakdown_minutes'], 45.0)
        self.assertEqual(metrics['operating_minutes'], 405.0)  # 450 - 45
        self.assertEqual(metrics['mtbf_minutes'], 202.5)      # 405 / 2
        self.assertEqual(metrics['mttr_minutes'], 22.5)       # 45 / 2
        self.assertAlmostEqual(metrics['failure_rate_per_hour'], 0.296, places=3)


class SMEDChangeoverTestCase(OperationsBaseTestCase):
    """Tests digital SMED 4-phase changeover stopwatch and setpoint transitions (F06)."""

    def test_smed_4_phase_changeover_lifecycle(self):
        # 1. Start changeover
        co = start_smed_changeover(self.line, self.product_b.id, self.operator_user, "Bottle 500ml to 1.5L swap")
        self.assertEqual(co.status, 'IN_PROGRESS')
        self.assertEqual(co.current_phase, 1)
        self.assertEqual(self.machine_capper.current_state.state_code, 'CHANGEOVER')

        # 2. Advance to Phase 2 (Mechanical Tooling)
        co = advance_smed_phase(co.id)
        self.assertEqual(co.current_phase, 2)
        self.assertGreater(co.phase1_duration_seconds, 0)

        # 3. Advance to Phase 3 (Recipe Loading)
        co = advance_smed_phase(co.id)
        self.assertEqual(co.current_phase, 3)
        self.assertGreater(co.phase2_duration_seconds, 0)

        # 4. Advance to Phase 4 (Test Run & Ramp-Up)
        co = advance_smed_phase(co.id)
        self.assertEqual(co.current_phase, 4)
        self.assertGreater(co.phase3_duration_seconds, 0)

        # 5. Complete changeover with ramp-up test pieces
        co = advance_smed_phase(co.id, rampup_units=50, rampup_scrap=2)
        self.assertEqual(co.status, 'COMPLETED')
        self.assertEqual(co.rampup_total_units, 50)
        self.assertEqual(co.rampup_scrap_units, 2)
        self.assertIsNotNone(co.completed_at)

        # Line product updated to Product B and machine returned to RUNNING
        self.line.refresh_from_db()
        self.assertEqual(self.line.current_product, self.product_b)
        self.machine_capper.refresh_from_db()
        self.assertEqual(self.machine_capper.current_state.state_code, 'RUNNING')


class ShiftHandoverTestCase(OperationsBaseTestCase):
    """Tests 3-step guided shift handover checklist and digital sign-off (F15)."""

    def test_shift_handover_3_step_workflow_and_lock(self):
        # 1. Retrieve draft handover
        handover = get_or_create_shift_handover(self.line, self.shift)
        self.assertEqual(handover.status, 'DRAFT')

        # 2. Digital sign-off and lock
        signed_handover = submit_and_lock_shift_handover(
            handover_id=handover.id,
            outgoing_user=self.supervisor_user,
            production_summary="Met 95% of target output without major stops.",
            safety_incidents="Zero safety incidents.",
            maintenance_notes="Capper spring tension checked.",
            quality_notes="Fill weights stable at 500.2g."
        )
        self.assertEqual(signed_handover.status, 'LOCKED')
        self.assertEqual(signed_handover.outgoing_supervisor, self.supervisor_user)
        self.assertIsNotNone(signed_handover.signed_at)
        self.assertIsNotNone(signed_handover.locked_at)


class UIZeroEmojisTestCase(OperationsBaseTestCase):
    """Verifies strict zero-emoji policy across all Batch 4 UI templates."""

    def test_zero_emojis_in_batch_4_views(self):
        self.client.force_login(self.admin_user)

        routes_to_test = [
            reverse('operator_home'),
            reverse('floor_home'),
            reverse('stoppages_home'),
            reverse('smed_home'),
            reverse('maintenance_home'),
            reverse('maintenance_spares'),
            reverse('maintenance_history'),
            reverse('shifts_home'),
        ]

        for url in routes_to_test:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Route {url} failed with status {response.status_code}")
            content = response.content.decode('utf-8')
            matches = EMOJI_PATTERN.findall(content)
            self.assertEqual(
                len(matches), 0,
                f"Forbidden decorative emojis found in {url}: {matches}"
            )
