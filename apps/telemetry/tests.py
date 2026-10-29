"""
Automated Test Suite for FactSense Telemetry Pipeline, OEE Engine, SSE & Demo Controller.
Strictly verifies Batch 3 acceptance criteria:
- Section 5: Telemetry Ingestion, 8-state machine, 180s pulse gap watchdog
- Section 6: ISO 22400 OEE Engine, TPM Six Big Losses waterfall, financial downtime costing
- Section 7.9: Demo Simulator controller, clock multiplier, 5 pre-built scenarios, data isolation
- Section 8: Zero-emoji compliance and server-side RBAC protection
"""

import json
import re
from datetime import time, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, Role, UserRoleAssignment
from apps.masterdata.models import Factory, Line, Machine, Shift, PlannedBreak, Product
from apps.telemetry.models import (
    MachineCurrentState, TelemetryReading, DowntimeEvent, SimulationScenarioState
)
from apps.telemetry.services.state_machine import (
    ingest_telemetry_reading, evaluate_watchdog_pulse_gap, map_state_to_tpm_loss
)
from apps.telemetry.services.oee_engine import calculate_line_oee
from apps.telemetry.services.losses_engine import (
    calculate_tpm_six_big_losses, calculate_financial_loss_cost
)
from apps.telemetry.services.simulator import (
    get_or_create_simulator, activate_scenario, step_simulation, reset_simulation
)

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u24C2]"
)


class TelemetryBaseTestCase(TestCase):
    """Base setup for telemetry tests with factory, line, machines, shifts, and personas."""

    def setUp(self):
        self.client = Client()

        # Seed roles
        self.controller_role, _ = Role.objects.get_or_create(
            code='controller',
            defaults={'name': 'Demo Controller', 'name_ar': 'متحكم المحاكاة', 'default_landing': '/controller/'}
        )
        self.admin_role, _ = Role.objects.get_or_create(
            code='admin',
            defaults={'name': 'System Administrator', 'name_ar': 'مدير النظام', 'default_landing': '/administration/'}
        )
        self.operator_role, _ = Role.objects.get_or_create(
            code='operator',
            defaults={'name': 'Machine Operator', 'name_ar': 'مشغل ماكينة', 'default_landing': '/operator/'}
        )

        # Seed users
        self.controller_user = User.objects.create_user(
            username='test_controller',
            password='Factsense@2026',
            first_name='Demo',
            last_name='Controller'
        )
        UserRoleAssignment.objects.create(user=self.controller_user, role=self.controller_role, is_active=True)

        self.operator_user = User.objects.create_user(
            username='test_operator',
            password='Factsense@2026',
            first_name='Line',
            last_name='Operator'
        )
        UserRoleAssignment.objects.create(user=self.operator_user, role=self.operator_role, is_active=True)

        self.admin_user = User.objects.create_user(
            username='test_admin',
            password='Factsense@2026',
            first_name='Admin',
            last_name='User'
        )
        UserRoleAssignment.objects.create(user=self.admin_user, role=self.admin_role, is_active=True)

        # Factory & Line setup
        self.factory = Factory.objects.create(
            code='FAC-CAI',
            name='Cairo Packaging Facility',
            name_ar='مصنع القاهرة للتعبئة',
            currency='EGP'
        )

        self.product = Product.objects.create(
            factory=self.factory,
            code='SKU-BOT-600',
            name='Mineral Water 600ml',
            unit_cost=Decimal('3.50'),
            scrap_cost=Decimal('1.20')
        )

        self.line = Line.objects.create(
            factory=self.factory,
            code='L1-WATER',
            name='Water Bottling Line 1',
            name_ar='خط تعبئة المياه 1',
            current_product=self.product
        )

        # Setup 3 machines: Blow Molder -> Filler (Bottleneck) -> Capper
        self.m1_blow = Machine.objects.create(
            line=self.line,
            code='BM-01',
            name='Rotary Blow Molder',
            category='BLOW_MOLDER',
            sequence_order=10,
            ideal_run_rate_cpm=140.0,
            criticality_rank='B'
        )
        self.m2_filler = Machine.objects.create(
            line=self.line,
            code='FL-01',
            name='Isobaric Rotary Filler',
            category='FILLER',
            sequence_order=20,
            ideal_run_rate_cpm=120.0,
            is_bottleneck=True,
            criticality_rank='A'
        )
        self.m3_capper = Machine.objects.create(
            line=self.line,
            code='CP-01',
            name='Rotary Capper',
            category='CAPPER',
            sequence_order=30,
            ideal_run_rate_cpm=130.0,
            criticality_rank='B'
        )

        # Designate line bottleneck
        self.line.bottleneck_machine = self.m2_filler
        self.line.save()

        # Shift setup: 8-hour shift (480 min total) with 30 min unpaid meal break = 450 min PPT
        self.shift = Shift.objects.create(
            factory=self.factory,
            code='MORN-1',
            name='Morning Production Shift',
            name_ar='وردية الصباح',
            start_time=time(7, 0),
            end_time=time(15, 0),
            unpaid_break_minutes=30,
            sequence=1
        )
        self.planned_break = PlannedBreak.objects.create(
            shift=self.shift,
            name='Lunch Break',
            start_time=time(12, 0),
            end_time=time(12, 30),
            duration_minutes=30,
            is_unpaid=True
        )


class TelemetryIngestionTestCase(TelemetryBaseTestCase):
    """Tests for POST /api/v1/telemetry/ingest/ and edge gateway payload validation."""

    def test_ingest_telemetry_valid_payload(self):
        url = reverse('api_telemetry_ingest')
        payload = {
            'machine_code': 'FL-01',
            'pulse_count': 15,
            'instant_cpm': 120.0,
            'state_code': 'RUNNING',
            'vibration': 0.85,
            'temperature': 42.5
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['machine_code'], 'FL-01')
        self.assertEqual(data['state_code'], 'RUNNING')
        self.assertEqual(data['current_speed_cpm'], 120.0)
        self.assertEqual(data['shift_pulse_count'], 15)

        # Check DB persistence
        reading = TelemetryReading.objects.filter(machine=self.m2_filler).latest('id')
        self.assertEqual(reading.pulse_count, 15)
        self.assertEqual(reading.instant_cpm, 120.0)
        self.assertEqual(reading.state_code, 'RUNNING')
        self.assertAlmostEqual(reading.vibration_rms, 0.85, places=2)
        self.assertAlmostEqual(reading.temperature_c, 42.5, places=1)
        self.assertFalse(reading.is_simulated)

        # Check MachineCurrentState
        curr = self.m2_filler.current_state
        self.assertEqual(curr.state_code, 'RUNNING')
        self.assertEqual(curr.shift_pulse_count, 15)

    def test_ingest_telemetry_invalid_json(self):
        url = reverse('api_telemetry_ingest')
        response = self.client.post(url, data="INVALID_NOT_JSON", content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid JSON', response.json()['message'])

    def test_ingest_telemetry_missing_machine_code(self):
        url = reverse('api_telemetry_ingest')
        response = self.client.post(url, data=json.dumps({'pulse_count': 1}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('machine_code is required', response.json()['message'])

    def test_ingest_telemetry_unknown_machine(self):
        url = reverse('api_telemetry_ingest')
        response = self.client.post(url, data=json.dumps({'machine_code': 'UNKNOWN-99'}), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertIn('not found', response.json()['message'])


class StateMachineAndWatchdogTestCase(TelemetryBaseTestCase):
    """Tests for 8-state machine transitions and 180s pulse gap watchdog."""

    def test_state_transitions_and_downtime_event_lifecycle(self):
        now = timezone.now()

        # Step 1: Start machine in RUNNING state
        ingest_telemetry_reading(self.m2_filler, pulse_count=20, instant_cpm=120.0, state_code='RUNNING', timestamp=now)
        self.assertEqual(self.m2_filler.current_state.state_code, 'RUNNING')
        self.assertEqual(DowntimeEvent.objects.filter(machine=self.m2_filler).count(), 0)

        # Step 2: Machine stops with UNPLANNED_DOWNTIME at now + 5 min
        t_stop = now + timedelta(minutes=5)
        ingest_telemetry_reading(self.m2_filler, pulse_count=0, instant_cpm=0.0, state_code='UNPLANNED_DOWNTIME', timestamp=t_stop)
        self.m2_filler.current_state.refresh_from_db()
        self.assertEqual(self.m2_filler.current_state.state_code, 'UNPLANNED_DOWNTIME')

        # Verify active open DowntimeEvent was created
        open_events = DowntimeEvent.objects.filter(machine=self.m2_filler, end_time__isnull=True)
        self.assertEqual(open_events.count(), 1)
        event = open_events.first()
        self.assertEqual(event.state_code, 'UNPLANNED_DOWNTIME')
        self.assertEqual(event.tpm_loss_type, 'AVAILABILITY_BREAKDOWN')
        self.assertFalse(event.is_planned)

        # Step 3: Machine resumes RUNNING at now + 15 min (10 min downtime)
        t_resume = now + timedelta(minutes=15)
        ingest_telemetry_reading(self.m2_filler, pulse_count=10, instant_cpm=120.0, state_code='RUNNING', timestamp=t_resume)
        self.m2_filler.current_state.refresh_from_db()

        # Verify previous DowntimeEvent was closed and duration recorded
        event.refresh_from_db()
        self.assertIsNotNone(event.end_time)
        self.assertEqual(event.duration_seconds, 600)  # 10 minutes * 60s
        self.assertEqual(self.m2_filler.current_state.state_code, 'RUNNING')

    def test_state_mapping_to_tpm_losses(self):
        self.assertEqual(map_state_to_tpm_loss('UNPLANNED_DOWNTIME'), 'AVAILABILITY_BREAKDOWN')
        self.assertEqual(map_state_to_tpm_loss('CHANGEOVER'), 'AVAILABILITY_CHANGEOVER')
        self.assertEqual(map_state_to_tpm_loss('MICRO_STOP'), 'PERFORMANCE_MINOR_STOP')
        self.assertEqual(map_state_to_tpm_loss('BLOCKED'), 'PERFORMANCE_MINOR_STOP')
        self.assertEqual(map_state_to_tpm_loss('STARVED'), 'PERFORMANCE_MINOR_STOP')
        self.assertEqual(map_state_to_tpm_loss('NO_DATA'), 'AVAILABILITY_BREAKDOWN')

    def test_watchdog_pulse_gap_trigger_over_180s(self):
        # Setup running state with last pulse 200 seconds ago
        past_time = timezone.now() - timedelta(seconds=200)
        curr, _ = MachineCurrentState.objects.get_or_create(
            machine=self.m1_blow,
            defaults={
                'state_code': 'RUNNING',
                'current_speed_cpm': 140.0,
                'last_pulse_at': past_time,
                'last_state_change': past_time
            }
        )
        curr.state_code = 'RUNNING'
        curr.last_pulse_at = past_time
        curr.save()

        # Run watchdog evaluator
        res = evaluate_watchdog_pulse_gap(self.m1_blow)
        self.assertIsNotNone(res)
        self.assertEqual(res.state_code, 'UNPLANNED_DOWNTIME')
        self.assertEqual(res.current_speed_cpm, 0.0)

        # Check auto-opened downtime event
        event = DowntimeEvent.objects.filter(machine=self.m1_blow, end_time__isnull=True).first()
        self.assertIsNotNone(event)
        self.assertIn('watchdog', event.notes.lower())

    def test_watchdog_no_trigger_within_window(self):
        recent_time = timezone.now() - timedelta(seconds=60)
        curr, _ = MachineCurrentState.objects.get_or_create(
            machine=self.m1_blow,
            defaults={
                'state_code': 'RUNNING',
                'current_speed_cpm': 140.0,
                'last_pulse_at': recent_time
            }
        )
        curr.state_code = 'RUNNING'
        curr.last_pulse_at = recent_time
        curr.save()

        res = evaluate_watchdog_pulse_gap(self.m1_blow)
        self.assertEqual(res.state_code, 'RUNNING')
        self.assertEqual(DowntimeEvent.objects.filter(machine=self.m1_blow).count(), 0)


class ISO22400CalculationTestCase(TelemetryBaseTestCase):
    """
    Tests ISO 22400 OEE mathematical engine against reproducible test fixtures.
    """

    def test_iso22400_known_numerical_fixture(self):
        """
        Verified Reproducible Fixture:
        - Planned Production Time (PPT) = 450 minutes (480 min shift - 30 min unpaid break).
        - Availability loss = 30 min breakdown + 15 min changeover = 45 minutes loss (2700s).
        - Operating Time = 450 - 45 = 405 minutes.
        - Availability = 405 / 450 = 0.90 (90.0%).
        - Bottleneck machine: ideal rate = 120 CPM.
        - Expected units = 405 min * 120 CPM = 48,600 units.
        - Total pulses recorded: 43,740 units.
        - Performance = 43,740 / 48,600 = 0.90 (90.0%).
        - Quality: 43,740 total, 874 scrap, 42,866 good units.
        - Quality = 42,866 / 43,740 = 0.98 (98.0%).
        - Overall OEE = 0.90 * 0.90 * 0.98 = 0.7938 -> 79.4%.
        """
        now = timezone.now()

        # 1. Create simulated availability loss events on bottleneck machine
        DowntimeEvent.objects.create(
            machine=self.m2_filler,
            line=self.line,
            state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=45),
            end_time=now - timedelta(minutes=15),
            duration_seconds=1800,  # 30 min breakdown
            tpm_loss_type='AVAILABILITY_BREAKDOWN',
            is_simulated=False
        )
        DowntimeEvent.objects.create(
            machine=self.m2_filler,
            line=self.line,
            state_code='CHANGEOVER',
            start_time=now - timedelta(minutes=15),
            end_time=now,
            duration_seconds=900,  # 15 min changeover
            tpm_loss_type='AVAILABILITY_CHANGEOVER',
            is_simulated=False
        )

        # 2. Update bottleneck machine state with production counts
        curr, _ = MachineCurrentState.objects.get_or_create(machine=self.m2_filler)
        curr.shift_pulse_count = 43740
        curr.shift_good_count = 42866
        curr.shift_scrap_count = 874
        curr.is_simulated = False
        curr.save()

        # 3. Calculate OEE
        result = calculate_line_oee(self.line, shift=self.shift, is_simulated=False)

        self.assertEqual(result['planned_production_minutes'], 450.0)
        self.assertEqual(result['operating_minutes'], 405.0)
        self.assertEqual(result['availability'], 90.0)
        self.assertEqual(result['performance'], 90.0)
        self.assertEqual(result['quality'], 98.0)
        self.assertEqual(result['oee'], 79.4)
        self.assertEqual(result['bottleneck_code'], 'FL-01')
        self.assertTrue(result['is_bottleneck_governed'])

    def test_zero_denominator_safety(self):
        """Zero planned time or zero counts should return clean zero or default without crashing."""
        curr, _ = MachineCurrentState.objects.get_or_create(machine=self.m2_filler)
        curr.shift_pulse_count = 0
        curr.shift_scrap_count = 0
        curr.save()

        result = calculate_line_oee(self.line, shift=None, is_simulated=False)
        self.assertIsNotNone(result['oee'])
        self.assertEqual(result['total_units'], 0)
        self.assertEqual(result['quality'], 100.0)  # baseline when zero units

    def test_performance_over_100_notice(self):
        """If machine runs faster than rated CPM, notice is flagged and overall OEE is capped safely."""
        curr, _ = MachineCurrentState.objects.get_or_create(machine=self.m2_filler)
        curr.shift_pulse_count = 60000  # Above expected 54,000
        curr.shift_scrap_count = 0
        curr.save()

        result = calculate_line_oee(self.line, shift=self.shift, is_simulated=False)
        self.assertGreater(result['performance'], 100.0)
        self.assertIsNotNone(result['performance_notice'])


class TPMLossesAndCostingTestCase(TelemetryBaseTestCase):
    """Tests TPM Six Big Losses allocation and financial costing."""

    def test_tpm_six_big_losses_allocation(self):
        now = timezone.now()
        DowntimeEvent.objects.create(
            machine=self.m2_filler,
            line=self.line,
            state_code='UNPLANNED_DOWNTIME',
            start_time=now - timedelta(minutes=40),
            end_time=now - timedelta(minutes=20),
            duration_seconds=1200,  # 20 min
            tpm_loss_type='AVAILABILITY_BREAKDOWN',
            is_simulated=False
        )
        DowntimeEvent.objects.create(
            machine=self.m2_filler,
            line=self.line,
            state_code='MICRO_STOP',
            start_time=now - timedelta(minutes=10),
            end_time=now - timedelta(minutes=5),
            duration_seconds=300,  # 5 min
            tpm_loss_type='PERFORMANCE_MINOR_STOP',
            is_simulated=False
        )

        waterfall = calculate_tpm_six_big_losses(self.line, shift=self.shift, is_simulated=False)
        self.assertEqual(waterfall['unplanned_breakdown_minutes'], 20.0)
        self.assertEqual(waterfall['minor_stoppages_minutes'], 5.0)
        self.assertGreater(waterfall['net_productive_minutes'], 0)
        self.assertEqual(len(waterfall['categories']), 7)

    def test_financial_loss_cost_calculation(self):
        """
        Downtime: 60 minutes
        Scrap: 100 units
        Ideal CPM: 120
        Profit per unit: 3.50 * 0.35 = 1.225
        Opportunity Loss = 60 * 120 * 1.225 = 8,820.00 EGP
        Direct Scrap Loss = 100 * 1.20 = 120.00 EGP
        Total = 8,940.00 EGP
        """
        cost = calculate_financial_loss_cost(self.line, downtime_minutes=60, scrap_units=100)
        self.assertEqual(cost['downtime_minutes'], 60)
        self.assertEqual(cost['scrap_units'], 100)
        self.assertEqual(cost['direct_scrap_loss'], 120.00)
        self.assertEqual(cost['opportunity_loss'], 8820.00)
        self.assertEqual(cost['total_loss_cost'], 8940.00)
        self.assertEqual(cost['currency'], 'EGP')


class SimulatorEngineTestCase(TelemetryBaseTestCase):
    """Tests 5 pre-built simulation scenarios, clock multiplier, and data isolation."""

    def test_simulation_clock_controls(self):
        sim = get_or_create_simulator(self.line)
        self.assertEqual(sim.clock_multiplier, 1.0)
        self.assertTrue(sim.is_running)

        # Pause simulation
        sim.clock_multiplier = 0.0
        sim.is_running = False
        sim.save()
        step_res = step_simulation(self.line, delta_seconds=10)
        self.assertEqual(step_res['status'], 'paused')

        # Fast forward (5x)
        sim.clock_multiplier = 5.0
        sim.is_running = True
        sim.save()
        step_res = step_simulation(self.line, delta_seconds=10)
        self.assertEqual(step_res['status'], 'stepped')
        self.assertEqual(step_res['effective_dt'], 50.0)

    def test_scenario_cap_chute_jam(self):
        activate_scenario(self.line, 'CAP_CHUTE_JAM')
        self.m3_capper.refresh_from_db()
        self.m2_filler.refresh_from_db()

        self.assertEqual(self.m3_capper.current_state.state_code, 'UNPLANNED_DOWNTIME')
        self.assertEqual(self.m2_filler.current_state.state_code, 'BLOCKED')

    def test_scenario_overfill_giveaway_drift(self):
        activate_scenario(self.line, 'OVERFILL_GIVEAWAY_DRIFT')
        sim = get_or_create_simulator(self.line)
        self.assertEqual(sim.active_scenario, 'OVERFILL_GIVEAWAY_DRIFT')
        self.m2_filler.refresh_from_db()
        self.assertEqual(self.m2_filler.current_state.state_code, 'RUNNING')

    def test_scenario_mechanical_breakdown(self):
        activate_scenario(self.line, 'MECHANICAL_BREAKDOWN')
        self.m1_blow.refresh_from_db()
        self.m2_filler.refresh_from_db()

        self.assertEqual(self.m1_blow.current_state.state_code, 'UNPLANNED_DOWNTIME')
        self.assertEqual(self.m2_filler.current_state.state_code, 'STARVED')

    def test_scenario_defect_burst(self):
        curr, _ = MachineCurrentState.objects.get_or_create(machine=self.m2_filler)
        curr.shift_scrap_count = 5
        curr.save()

        activate_scenario(self.line, 'DEFECT_BURST')
        curr.refresh_from_db()
        self.assertEqual(curr.shift_scrap_count, 30)  # 5 + 25

    def test_scenario_golden_run(self):
        activate_scenario(self.line, 'GOLDEN_RUN')
        for m in self.line.machines.all():
            m.refresh_from_db()
            self.assertEqual(m.current_state.state_code, 'RUNNING')
            self.assertEqual(m.current_state.current_speed_cpm, m.ideal_run_rate_cpm)

    def test_simulation_data_isolation(self):
        """Simulated events and readings must have is_simulated=True and not bleed into live queries."""
        activate_scenario(self.line, 'CAP_CHUTE_JAM')

        simulated_events = DowntimeEvent.objects.filter(line=self.line, is_simulated=True)
        live_events = DowntimeEvent.objects.filter(line=self.line, is_simulated=False)

        self.assertGreater(simulated_events.count(), 0)
        self.assertEqual(live_events.count(), 0)

        # Reset simulation
        reset_simulation(self.line)
        self.assertEqual(DowntimeEvent.objects.filter(line=self.line, is_simulated=True).count(), 0)
        self.m2_filler.current_state.refresh_from_db()
        self.assertEqual(self.m2_filler.current_state.state_code, 'RUNNING')
        self.assertEqual(self.m2_filler.current_state.shift_pulse_count, 0)


class TelemetryAPIsAndSSETestCase(TelemetryBaseTestCase):
    """Tests for live JSON snapshot API, SSE stream, and KPI calculation APIs."""

    def test_telemetry_live_api(self):
        url = reverse('api_telemetry_live', kwargs={'line_code': self.line.code})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['line_code'], self.line.code)
        self.assertEqual(data['bottleneck_code'], 'FL-01')
        self.assertEqual(len(data['machines']), 3)
        self.assertIn('oee', data)

    def test_telemetry_stream_sse_endpoint(self):
        url = f"{reverse('api_telemetry_stream', kwargs={'line_code': self.line.code})}?limit=1&delay=0"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')

        # Read first SSE frame
        content = b"".join(response.streaming_content).decode('utf-8')
        self.assertIn('event: telemetry', content)
        self.assertIn('"line_code": "L1-WATER"', content)

    def test_calculation_rest_apis(self):
        kpi_url = reverse('api_line_kpi', kwargs={'line_code': self.line.code})
        kpi_res = self.client.get(kpi_url)
        self.assertEqual(kpi_res.status_code, 200)
        self.assertIn('oee', kpi_res.json())

        waterfall_url = reverse('api_line_waterfall', kwargs={'line_code': self.line.code})
        wf_res = self.client.get(waterfall_url)
        self.assertEqual(wf_res.status_code, 200)
        self.assertIn('categories', wf_res.json())

        hourly_url = reverse('api_line_hourly', kwargs={'line_code': self.line.code})
        hr_res = self.client.get(hourly_url)
        self.assertEqual(hr_res.status_code, 200)
        self.assertIn('hourly_trend', hr_res.json())


class ControllerViewsAndRBACTestCase(TelemetryBaseTestCase):
    """Tests RBAC security, controller form submissions, and zero-emoji UI."""

    def test_controller_rbac_forbidden_for_operator(self):
        self.client.force_login(self.operator_user)
        response = self.client.get(reverse('controller_home'))
        self.assertEqual(response.status_code, 403)

    def test_controller_accessible_for_controller_and_admin(self):
        # Test controller persona
        self.client.force_login(self.controller_user)
        response = self.client.get(reverse('controller_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DEMO MODE ACTIVE')
        self.assertContains(response, 'Water Bottling Line 1')

        # Test admin persona
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('controller_home'))
        self.assertEqual(response.status_code, 200)

    def test_controller_scenario_apply_action(self):
        self.client.force_login(self.controller_user)
        url = reverse('controller_scenario_apply')
        response = self.client.post(url, {
            'line_id': self.line.id,
            'scenario_key': 'DEFECT_BURST'
        })
        self.assertEqual(response.status_code, 302)
        sim = get_or_create_simulator(self.line)
        self.assertEqual(sim.active_scenario, 'DEFECT_BURST')

    def test_controller_clock_apply_action(self):
        self.client.force_login(self.controller_user)
        url = reverse('controller_clock_apply')
        response = self.client.post(url, {
            'line_id': self.line.id,
            'clock_multiplier': '5.0'
        })
        self.assertEqual(response.status_code, 302)
        sim = get_or_create_simulator(self.line)
        self.assertEqual(sim.clock_multiplier, 5.0)

    def test_controller_step_action(self):
        self.client.force_login(self.controller_user)
        url = reverse('controller_step_action')
        response = self.client.post(url, {'line_id': self.line.id})
        self.assertEqual(response.status_code, 302)
        sim = get_or_create_simulator(self.line)
        self.assertGreater(sim.tick_count, 0)

    def test_controller_reset_action(self):
        self.client.force_login(self.controller_user)
        url = reverse('controller_reset_action')
        response = self.client.post(url, {'line_id': self.line.id})
        self.assertEqual(response.status_code, 302)
        sim = get_or_create_simulator(self.line)
        self.assertEqual(sim.active_scenario, 'NONE')
        self.assertEqual(sim.tick_count, 0)

    def test_controller_override_machine_action(self):
        self.client.force_login(self.controller_user)
        url = reverse('controller_override_machine')
        response = self.client.post(url, {
            'machine_id': self.m2_filler.id,
            'state_code': 'SLOW',
            'current_speed_cpm': '60.0',
            'vibration_rms': '1.5',
            'temperature_c': '48.0'
        })
        self.assertEqual(response.status_code, 302)
        curr = self.m2_filler.current_state
        self.assertEqual(curr.state_code, 'SLOW')
        self.assertEqual(curr.current_speed_cpm, 60.0)

    def test_controller_ui_zero_emojis(self):
        self.client.force_login(self.controller_user)
        response = self.client.get(reverse('controller_home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        matches = EMOJI_PATTERN.findall(content)
        self.assertEqual(
            len(matches), 0,
            f"Found forbidden emojis in controller template: {matches}"
        )
