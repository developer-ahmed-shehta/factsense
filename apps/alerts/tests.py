"""
Unit and Integration Tests for Real-Time Alerts, Alarm Storm Engine & Deduplication (F08).
Strictly verifies:
- Configurable Alert Rules and thresholds
- Alarm storm deduplication and cooldown suppression window
- Auto-resolve watchdog tracking telemetry recovery
- Direct escalation to formal MaintenanceTicket
- Global Notification Drawer and unread count API
- Zero emojis compliance across all alert templates
"""

import re
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine
from apps.telemetry.models import MachineCurrentState
from apps.alerts.models import AlertRule, AlertIncident, AlertSuppressionLog
from apps.alerts.services.alert_engine import (
    trigger_or_deduplicate_alert, auto_resolve_watchdog,
    acknowledge_alert, resolve_alert, escalate_to_maintenance_ticket,
    get_active_alerts_summary
)

EMOJI_PATTERN = re.compile(
    r'[\U00010000-\U0010ffff]'
    r'|[\u2600-\u26FF]'
    r'|[\u2700-\u27BF]'
    r'|[\u2B50-\u2B55]'
    r'|[\u23E9-\u23FA]'
)


class AlertsEngineTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Create Factory, Line, Machine
        self.factory = Factory.objects.create(name='Alerts Factory', code='ALT-FAC-01')
        self.line = Line.objects.create(factory=self.factory, name='Packaging Line', code='LINE-PKG')
        self.capper = Machine.objects.create(
            line=self.line, name='Rotary Capper', code='CAP-01',
            category='CAPPER', sequence_order=3, ideal_run_rate_cpm=120
        )

        # Create MachineCurrentState
        self.capper_state = MachineCurrentState.objects.create(
            machine=self.capper,
            state_code='UNPLANNED_DOWNTIME',
            current_speed_cpm=0.0,
            temperature_c=68.5,
            vibration_rms=2.1,
            last_state_change=timezone.now() - timedelta(minutes=20),
        )

        # Create Alert Rule
        self.rule_downtime = AlertRule.objects.create(
            name='Capper Extended Downtime',
            scope='MACHINE',
            machine=self.capper,
            line=self.line,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            threshold_value=Decimal('15.0'),
            duration_seconds=900,
            cooldown_minutes=10,
            auto_resolve=True,
            is_active=True,
        )

        # Create Supervisor User & Admin User
        self.supervisor_role = Role.objects.get_or_create(code='supervisor', defaults={'name': 'Shift Supervisor'})[0]
        self.admin_role = Role.objects.get_or_create(code='admin', defaults={'name': 'System Administrator'})[0]

        self.supervisor_user = User.objects.create_user(username='supervisor_alert_test', password='password123')
        UserRoleAssignment.objects.create(user=self.supervisor_user, role=self.supervisor_role)

        self.admin_user = User.objects.create_user(username='admin_alert_test', password='password123')
        UserRoleAssignment.objects.create(user=self.admin_user, role=self.admin_role)

    def test_alert_rule_creation(self):
        """Verifies AlertRule model initialization and attributes."""
        self.assertEqual(self.rule_downtime.severity, 'CRITICAL')
        self.assertEqual(self.rule_downtime.cooldown_minutes, 10)
        self.assertTrue(self.rule_downtime.auto_resolve)

    def test_alert_trigger_and_alarm_storm_deduplication(self):
        """
        Verifies alarm storm suppression:
        First trigger creates Incident (occurrences_count = 1).
        Second trigger within cooldown deduplicates and increments occurrences_count to 2
        without creating a new duplicate incident row.
        """
        # First trigger
        inc1, created1 = trigger_or_deduplicate_alert(
            machine=self.capper,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            title='Capper Jam Stop',
            message='Capper stopped over 15 minutes.',
            rule=self.rule_downtime
        )
        self.assertTrue(created1)
        self.assertEqual(inc1.occurrences_count, 1)
        self.assertEqual(inc1.status, 'ACTIVE')

        # Second trigger 2 minutes later (within 10m cooldown window)
        inc2, created2 = trigger_or_deduplicate_alert(
            machine=self.capper,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            title='Capper Jam Stop Recurred',
            message='Capper still stopped.',
            rule=self.rule_downtime
        )
        self.assertFalse(created2)
        self.assertEqual(inc2.id, inc1.id)
        self.assertEqual(inc2.occurrences_count, 2)

        # Exactly 1 incident in database, but 1 suppression log
        self.assertEqual(AlertIncident.objects.filter(machine=self.capper).count(), 1)
        self.assertEqual(AlertSuppressionLog.objects.filter(incident=inc1).count(), 1)

    def test_auto_resolve_watchdog_upon_telemetry_recovery(self):
        """
        Verifies that auto_resolve_watchdog automatically resolves active downtime alerts
        when machine state returns to RUNNING.
        """
        inc, _ = trigger_or_deduplicate_alert(
            machine=self.capper,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            title='Capper Breakdown',
            message='Capper is down.',
            rule=self.rule_downtime
        )
        self.assertEqual(inc.status, 'ACTIVE')

        # Simulate machine resuming RUNNING state
        self.capper_state.state_code = 'RUNNING'
        self.capper_state.current_speed_cpm = 110.0
        self.capper_state.save()

        # Run watchdog
        resolved = auto_resolve_watchdog(machine=self.capper)
        self.assertEqual(len(resolved), 1)

        inc.refresh_from_db()
        self.assertEqual(inc.status, 'RESOLVED')
        self.assertIn('Auto-resolved by Telemetry Watchdog', inc.resolution_note)

    def test_escalate_alert_to_maintenance_ticket(self):
        """
        Verifies escalating an alert creates a formal MaintenanceTicket
        with force_lockout for CRITICAL alerts and binds alert.spawned_ticket.
        """
        inc, _ = trigger_or_deduplicate_alert(
            machine=self.capper,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            title='Severe Capper Chuck Failure',
            message='Chuck spring snapped.',
            rule=self.rule_downtime
        )

        ticket = escalate_to_maintenance_ticket(inc.id, self.supervisor_user)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.machine, self.capper)
        self.assertEqual(ticket.priority, 'CRITICAL')
        self.assertTrue(ticket.force_lockout)

        inc.refresh_from_db()
        self.assertEqual(inc.spawned_ticket, ticket)
        self.assertEqual(inc.status, 'ACKNOWLEDGED')

    def test_notification_drawer_and_count_api(self):
        """Verifies GET /alerts/api/count/ and /alerts/api/drawer/ endpoints."""
        trigger_or_deduplicate_alert(
            machine=self.capper,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            title='Capper Alarm',
            message='Stopped.',
            rule=self.rule_downtime
        )

        # Count API
        url_count = reverse('alert_unread_count_api')
        res_count = self.client.get(url_count)
        self.assertEqual(res_count.status_code, 200)
        data = res_count.json()
        self.assertGreaterEqual(data['total_active'], 1)
        self.assertGreaterEqual(data['critical_count'], 1)

        # Drawer HTML API
        url_drawer = reverse('alert_drawer_api')
        res_drawer = self.client.get(url_drawer)
        self.assertEqual(res_drawer.status_code, 200)
        html = res_drawer.content.decode('utf-8')
        self.assertIn('Capper Alarm', html)
        self.assertIn('CAP-01', html)

    def test_zero_emojis_in_alerts_templates(self):
        """Verifies strict zero-emoji policy across Batch 5 alerts views."""
        trigger_or_deduplicate_alert(
            machine=self.capper,
            rule_type='DOWNTIME_DURATION',
            severity='CRITICAL',
            title='Capper Alarm',
            message='Stopped.',
            rule=self.rule_downtime
        )

        self.client.force_login(self.admin_user)
        urls = [
            reverse('alerts_home'),
            reverse('alerts_home') + '?status=RULES',
            reverse('alert_drawer_api'),
        ]

        for u in urls:
            resp = self.client.get(u)
            self.assertEqual(resp.status_code, 200, f"Route {u} returned {resp.status_code}")
            content = resp.content.decode('utf-8')
            matches = EMOJI_PATTERN.findall(content)
            self.assertEqual(len(matches), 0, f"Found decorative emojis in {u}: {matches}")
