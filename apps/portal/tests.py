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
from apps.masterdata.models import Factory, Line, Machine, Shift, Product
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
