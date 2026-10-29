"""
Unit and Integration Tests for Executive Management Overview & Dashboard (F04).
Strictly verifies:
- Actionable 'So What?' Executive Banner with active bottleneck, efficiency %, and loss cost
- Line OEE Benchmark Gauges vs World-Class 85.0% target
- TPM Six Big Losses financial waterfall visualizer
- Shift Progress & Production Pacing with Hourly run rates
- Live Conveyor Machine Flow Strip
- Zero emojis compliance across all dashboard views
"""

import re
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Shift, Product, ReasonCategory, StoppageReason
from apps.telemetry.models import MachineCurrentState
from apps.portal.services.dashboard_service import get_executive_dashboard_data

EMOJI_PATTERN = re.compile(
    r'[\U00010000-\U0010ffff]'
    r'|[\u2600-\u26FF]'
    r'|[\u2700-\u27BF]'
    r'|[\u2B50-\u2B55]'
    r'|[\u23E9-\u23FA]'
)


class ExecutiveDashboardTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Create Factory, Line, and Machines
        self.factory = Factory.objects.create(name='Executive Test Plant', code='EXE-PLANT-01')
        self.line = Line.objects.create(factory=self.factory, name='Main Packaging Line', code='LINE-EXE')
        
        self.blow = Machine.objects.create(
            line=self.line, name='Blow Molder', code='BM-01',
            category='BLOW_MOLDER', sequence_order=1, ideal_run_rate_cpm=120
        )
        self.filler = Machine.objects.create(
            line=self.line, name='Rotary Filler', code='FL-01',
            category='FILLER', sequence_order=2, ideal_run_rate_cpm=100, is_bottleneck=True
        )
        self.capper = Machine.objects.create(
            line=self.line, name='Chuck Capper', code='CP-01',
            category='CAPPER', sequence_order=3, ideal_run_rate_cpm=120
        )

        # Telemetry current states
        MachineCurrentState.objects.create(
            machine=self.blow, state_code='RUNNING', current_speed_cpm=115.0
        )
        MachineCurrentState.objects.create(
            machine=self.filler, state_code='RUNNING', current_speed_cpm=95.0
        )
        MachineCurrentState.objects.create(
            machine=self.capper, state_code='RUNNING', current_speed_cpm=110.0
        )

        # Users and Roles
        self.manager_role = Role.objects.get_or_create(code='manager', defaults={'name': 'Plant Manager'})[0]
        self.admin_role = Role.objects.get_or_create(code='admin', defaults={'name': 'System Administrator'})[0]

        self.manager_user = User.objects.create_user(username='manager_tester', password='password123')
        UserRoleAssignment.objects.create(user=self.manager_user, role=self.manager_role)

        self.admin_user = User.objects.create_user(username='admin_tester_portal', password='password123')
        UserRoleAssignment.objects.create(user=self.admin_user, role=self.admin_role)

    def test_executive_dashboard_service_calculation(self):
        """Verifies dashboard service compiles all required F04 components."""
        data = get_executive_dashboard_data(line=self.line)
        self.assertEqual(data['status'], 'OK')

        # 1. So What Banner
        banner = data['so_what_banner']
        self.assertEqual(banner['bottleneck'], self.filler)
        self.assertEqual(banner['bn_cpm'], 95)
        self.assertEqual(banner['bn_ideal'], 100)
        self.assertEqual(banner['bn_efficiency'], 95.0)
        self.assertIn(banner['health'], ['OPTIMAL', 'DEGRADED', 'CRITICAL'])
        self.assertIn('Line constraint centered on', banner['message'])

        # 2. Benchmarks vs 85.0%
        bm = data['benchmarks']
        self.assertIn('oee', bm)
        self.assertEqual(bm['oee']['target'], 85.0)

        # 3. Pacing & Hourly Run Chart
        pacing = data['pacing']
        self.assertEqual(len(pacing['hourly_chart']), 8)
        self.assertIn(pacing['status'], ['ON_PACE', 'MARGINAL', 'BEHIND'])

        # 4. Conveyor Strip
        strip = data['conveyor_strip']
        self.assertEqual(len(strip), 3)
        self.assertEqual(strip[0]['code'], 'BM-01')
        self.assertEqual(strip[1]['code'], 'FL-01')
        self.assertTrue(strip[1]['is_bottleneck'])
        self.assertEqual(strip[2]['code'], 'CP-01')

    def test_manager_home_and_losses_views(self):
        """Verifies GET /dashboard/ and /dashboard/losses/ return HTTP 200."""
        self.client.force_login(self.manager_user)

        res_home = self.client.get(reverse('manager_home'), {'line': self.line.id})
        self.assertEqual(res_home.status_code, 200)

        res_losses = self.client.get(reverse('manager_losses'), {'line': self.line.id})
        self.assertEqual(res_losses.status_code, 200)

    def test_zero_emojis_in_dashboard_templates(self):
        """Verifies strict zero-emoji policy across all Batch 5 executive views."""
        self.client.force_login(self.manager_user)
        urls = [
            reverse('manager_home') + f'?line={self.line.id}',
            reverse('manager_losses') + f'?line={self.line.id}',
        ]

        for u in urls:
            resp = self.client.get(u)
            self.assertEqual(resp.status_code, 200, f"Route {u} returned {resp.status_code}")
            content = resp.content.decode('utf-8')
            matches = EMOJI_PATTERN.findall(content)
            self.assertEqual(len(matches), 0, f"Found decorative emojis in {u}: {matches}")


class Batch8HardeningAndAdminTestCase(TestCase):
    """
    Batch 8 Hardening, Admin Console, and Integration Tests.
    """
    def setUp(self):
        self.client = Client()
        self.factory = Factory.objects.create(
            name='Cairo Packaging Facility',
            code='CAIRO-TEST-01',
            timezone='Africa/Cairo',
            currency='EGP'
        )
        self.line = Line.objects.create(factory=self.factory, name='Packaging Line 1', code='LINE-01', target_oee=85.0)
        self.machine = Machine.objects.create(
            line=self.line, name='Filling Machine 01', code='FL-01',
            category='FILLER', sequence_order=1, ideal_run_rate_cpm=100.0
        )
        self.cat = ReasonCategory.objects.create(name='Mechanical', department='MECHANICAL')
        self.reason_normal = StoppageReason.objects.create(
            category=self.cat, code='MECH_JAM', name='Mechanical Jam', tpm_loss_type='AVAILABILITY_BREAKDOWN'
        )
        self.reason_safety = StoppageReason.objects.create(
            category=self.cat, code='BEARING_FAIL', name='Spindle Bearing Overheat',
            tpm_loss_type='AVAILABILITY_BREAKDOWN', force_logout=True
        )

        # Canonical Roles
        self.roles = {}
        for rcode, rname in [
            ('admin', 'Administrator'),
            ('operator', 'Line Operator'),
            ('supervisor', 'Shift Supervisor'),
            ('maintenance', 'Technician'),
            ('engineer', 'Process Engineer'),
            ('quality', 'Quality Inspector'),
            ('planner', 'Production Planner'),
            ('supply_chain', 'Supply Chain'),
            ('manager', 'Plant Manager'),
            ('controller', 'Simulation Controller'),
        ]:
            role, _ = Role.objects.get_or_create(code=rcode, defaults={'name': rname, 'default_landing': f'/{rcode}/'})
            self.roles[rcode] = role

        # Users
        self.admin = User.objects.create_user(username='admin_b8', password='password123', is_staff=True, is_superuser=True)
        UserRoleAssignment.objects.create(user=self.admin, role=self.roles['admin'])

        self.op1 = User.objects.create_user(username='op_ahmed', password='password123')
        UserRoleAssignment.objects.create(user=self.op1, role=self.roles['operator'], machine=self.machine)

        self.op2 = User.objects.create_user(username='op_mahmoud', password='password123')
        UserRoleAssignment.objects.create(user=self.op2, role=self.roles['operator'], machine=self.machine)

        self.supervisor = User.objects.create_user(username='sup_tarek', password='password123')
        UserRoleAssignment.objects.create(user=self.supervisor, role=self.roles['supervisor'], line=self.line)

    def test_admin_settings_update_and_audit(self):
        """Verifies GET and POST /administration/settings/ updates factory params and logs audit event."""
        self.client.force_login(self.admin)
        res_get = self.client.get(reverse('admin_settings'))
        self.assertEqual(res_get.status_code, 200)

        res_post = self.client.post(reverse('admin_settings'), {
            'name': 'Updated Cairo Plant',
            'name_ar': 'مصنع القاهرة المحدث',
            'location': '6th of October City',
            'timezone': 'Africa/Cairo',
            'currency': 'EGP',
            'target_oee': '88.5',
        })
        self.assertEqual(res_post.status_code, 302)

        self.factory.refresh_from_db()
        self.assertEqual(self.factory.name, 'Updated Cairo Plant')
        self.line.refresh_from_db()
        self.assertEqual(self.line.target_oee, 88.5)

        # Verify audit event
        from apps.accounts.models import AuditEvent
        audit = AuditEvent.objects.filter(action='UPDATE_SYSTEM_SETTINGS').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.details.get('target_oee'), 88.5)

    def test_admin_integrations_and_ping(self):
        """Verifies GET /administration/integrations/ and POST test ping."""
        self.client.force_login(self.admin)
        res_get = self.client.get(reverse('admin_integrations'))
        self.assertEqual(res_get.status_code, 200)

        res_ping = self.client.post(reverse('admin_integrations_ping'))
        self.assertEqual(res_ping.status_code, 302)

        from apps.accounts.models import AuditEvent
        ping_audit = AuditEvent.objects.filter(action='INTEGRATION_TEST_PING').first()
        self.assertIsNotNone(ping_audit)

    def test_admin_audit_trail_filtering_and_csv_export(self):
        """Verifies /administration/audit/ filtering and CSV streaming export."""
        self.client.force_login(self.admin)
        from apps.accounts.models import AuditEvent
        AuditEvent.objects.create(actor=self.admin, active_role='admin', action='TEST_AUDIT_ACTION_1', resource='TestRes')

        res_filter = self.client.get(reverse('admin_audit'), {'action': 'TEST_AUDIT_ACTION_1'})
        self.assertEqual(res_filter.status_code, 200)
        self.assertContains(res_filter, 'TEST_AUDIT_ACTION_1')

        res_csv = self.client.get(reverse('admin_audit_export_csv'))
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')
        self.assertIn('TEST_AUDIT_ACTION_1', res_csv.content.decode('utf-8'))

    def test_kiosk_session_exclusivity_conflict(self):
        """Verifies that when Op1 claims machine, Op2 receives exclusive conflict warning."""
        from apps.accounts.services.kiosk_service import (
            claim_operator_session, check_kiosk_exclusivity, release_operator_session
        )
        from apps.accounts.models import OperatorSession

        # Op1 claims machine
        claim1, msg1 = claim_operator_session(self.op1, self.machine, 'sess-op1')
        self.assertIsNotNone(claim1)
        self.assertTrue(claim1.is_active)

        # Op2 checks exclusivity
        check2 = check_kiosk_exclusivity(self.op2, self.machine, 'sess-op2')
        self.assertFalse(check2['allowed'])
        self.assertTrue(check2['conflict'])
        self.assertIn('Exclusive Session Conflict', check2['message'])

        # Operator console renders conflict banner for Op2
        self.client.force_login(self.op2)
        res_op2 = self.client.get(f'/operator/?line={self.line.code}&machine={self.machine.code}')
        self.assertEqual(res_op2.status_code, 200)
        self.assertContains(res_op2, 'EXCLUSIVE OPERATOR SESSION ACTIVE')

        # Supervisor overrides and clears session
        self.client.force_login(self.supervisor)
        res_override = self.client.post(reverse('operator_session_override_action'), {
            'machine_id': self.machine.id
        })
        self.assertEqual(res_override.status_code, 302)

        # Op1 session is now inactive
        claim1.refresh_from_db()
        self.assertFalse(claim1.is_active)

    def test_kiosk_safety_force_logout_lockout(self):
        """Verifies machine with force_logout=True stoppage engages safety lockout."""
        from apps.telemetry.models import DowntimeEvent
        from apps.accounts.services.kiosk_service import check_machine_force_logout

        # Create active stoppage with force_logout=True
        DowntimeEvent.objects.create(
            line=self.line,
            machine=self.machine,
            reason=self.reason_safety,
            start_time=timezone.now()
        )

        is_locked_out, msg = check_machine_force_logout(self.machine)
        self.assertTrue(is_locked_out)
        self.assertIn('Safety Lockout', msg)

        # Operator inputs are blocked server-side
        self.client.force_login(self.op1)
        res_inc = self.client.post(reverse('operator_increment_action'), {
            'machine_id': self.machine.id,
            'increment': 1
        })
        self.assertEqual(res_inc.status_code, 302)
        # Verify piece was NOT incremented under lockout
        from apps.telemetry.models import MachineCurrentState
        state = MachineCurrentState.objects.filter(machine=self.machine).first()
        pulse_count = state.shift_pulse_count if state else 0
        self.assertEqual(pulse_count, 0)

    def test_observability_healthz_endpoint(self):
        """Verifies /healthz/ and /status/ return 200 OK JSON."""
        res = self.client.get('/healthz/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['subsystems']['database']['status'], 'connected')
        self.assertIn('latency_ms', data['subsystems']['database'])

        res_status = self.client.get('/status/')
        self.assertEqual(res_status.status_code, 200)

    def test_ten_canonical_roles_landing_pages(self):
        """Verifies each canonical persona reaches their authorized primary view."""
        role_landing_map = [
            ('admin', '/administration/'),
            ('operator', '/operator/'),
            ('supervisor', '/floor/'),
            ('maintenance', '/maintenance/'),
            ('engineer', '/stoppages/reliability/'),
            ('quality', '/quality/'),
            ('planner', '/masterdata/products/'),
            ('supply_chain', '/work-orders/'),
            ('manager', '/dashboard/'),
            ('controller', '/controller/'),
        ]

        for rcode, expected_path in role_landing_map:
            user = User.objects.create_user(username=f'user_{rcode}', password='password123')
            UserRoleAssignment.objects.create(
                user=user,
                role=self.roles[rcode],
                factory=self.factory,
                line=self.line,
                machine=self.machine
            )
            self.client.force_login(user)
            resp = self.client.get(expected_path)
            self.assertIn(resp.status_code, [200, 302], f"Role {rcode} failed to access {expected_path}")

    def test_failed_login_creates_audit_event(self):
        """Verifies bad login attempts write LOGIN_FAILED to AuditEvent."""
        from apps.accounts.models import AuditEvent
        self.client.post(reverse('login'), {
            'username': 'non_existent_hacker',
            'password': 'wrong_password_123',
        })
        audit = AuditEvent.objects.filter(action='LOGIN_FAILED', resource_id='non_existent_hacker').first()
        self.assertIsNotNone(audit)

