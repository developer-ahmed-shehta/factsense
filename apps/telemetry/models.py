"""
Models for FactSense Telemetry Ingestion, Machine States, and Simulation.
Implements Section 5 (Telemetry & State Machine) and Section 7.9 (Simulator Controller).
"""

import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.masterdata.models import Machine, Line, Shift, Product, ReasonCategory, StoppageReason

STATE_CHOICES = [
    ('RUNNING', 'Running (Producing at/near rated speed)'),
    ('UNPLANNED_DOWNTIME', 'Unplanned Downtime (Fault / Jam / Breakdown)'),
    ('PLANNED_DOWNTIME', 'Planned Downtime (Maintenance / CIP / Meeting)'),
    ('CHANGEOVER', 'Changeover (SMED Tooling / Recipe Swap)'),
    ('MICRO_STOP', 'Micro Stop (Momentary halt < 180s)'),
    ('BLOCKED', 'Blocked (Downstream conveyor/buffer full)'),
    ('STARVED', 'Starved (Upstream buffer empty)'),
    ('NO_DATA', 'No Data (Heartbeat timeout / Disconnected)'),
]

TPM_LOSS_CHOICES = [
    ('AVAILABILITY_BREAKDOWN', 'Unplanned Equipment Breakdown (Availability)'),
    ('AVAILABILITY_CHANGEOVER', 'Setup & Changeover Loss (Availability)'),
    ('PERFORMANCE_MINOR_STOP', 'Idling & Minor Micro-Stops (Performance)'),
    ('PERFORMANCE_SPEED_LOSS', 'Reduced Speed Loss (Performance)'),
    ('QUALITY_DEFECTS', 'Production Defect & Scrap (Quality)'),
    ('QUALITY_STARTUP_SCRAP', 'Startup Yield Reject Loss (Quality)'),
]

SCENARIO_CHOICES = [
    ('NONE', 'Baseline Normal Production'),
    ('CAP_CHUTE_JAM', 'Scenario 1: Cap Chute Jam (Capper fault, Filler blocked)'),
    ('OVERFILL_GIVEAWAY_DRIFT', 'Scenario 2: Overfill Giveaway Drift (+1.2g weight drift)'),
    ('MECHANICAL_BREAKDOWN', 'Scenario 3: Mechanical Breakdown (Blow molder stop, line starved)'),
    ('DEFECT_BURST', 'Scenario 4: Defect Burst (Spike of 25 label scrap defects)'),
    ('GOLDEN_RUN', 'Scenario 5: Golden Run (Target 95% OEE World Class)'),
]


class MachineCurrentState(models.Model):
    """
    Real-time state and counter cache for a machine asset.
    Updated 1 Hz via telemetry ingestion or simulation tick.
    """
    machine = models.OneToOneField(Machine, on_delete=models.CASCADE, related_name='current_state')
    state_code = models.CharField(max_length=30, choices=STATE_CHOICES, default='RUNNING')
    current_speed_cpm = models.FloatField(default=0.0, help_text="Instantaneous operating speed in units/minute")
    vibration_rms = models.FloatField(default=0.8, help_text="Vibration in mm/s RMS")
    temperature_c = models.FloatField(default=42.5, help_text="Operating temperature in °C")
    
    # Cumulative shift metrics
    shift_pulse_count = models.PositiveIntegerField(default=0, help_text="Total units passed photo-eye in shift")
    shift_good_count = models.PositiveIntegerField(default=0, help_text="Good accepted pieces in shift")
    shift_scrap_count = models.PositiveIntegerField(default=0, help_text="Scrap defect pieces in shift")

    # Context
    active_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    active_shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    is_simulated = models.BooleanField(default=False, help_text="Isolates synthetic simulation from live plant")

    last_pulse_at = models.DateTimeField(null=True, blank=True)
    last_state_change = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['machine__sequence_order']

    def __str__(self):
        sim = " [SIM]" if self.is_simulated else ""
        return f"{self.machine.code}: {self.state_code} @ {self.current_speed_cpm:.1f} CPM{sim}"

    @property
    def is_running(self):
        return self.state_code == 'RUNNING'

    @property
    def state(self):
        return self.state_code

    @property
    def current_cpm(self):
        return int(self.current_speed_cpm)

    @property
    def current_temperature_c(self):
        return self.temperature_c

    @property
    def current_vibration_rms(self):
        return self.vibration_rms

    @property
    def state_changed_at(self):
        return self.last_state_change

    @property
    def status_color(self):
        """Matches Industrial Semantic Design Tokens."""
        mapping = {
            'RUNNING': '#10B981',             # Emerald
            'UNPLANNED_DOWNTIME': '#EF4444',  # Rose
            'PLANNED_DOWNTIME': '#F59E0B',    # Amber
            'CHANGEOVER': '#8B5CF6',          # Purple
            'MICRO_STOP': '#F97316',          # Orange
            'BLOCKED': '#EAB308',             # Yellow
            'STARVED': '#A855F7',             # Violet
            'NO_DATA': '#6B7280',             # Slate
        }
        return mapping.get(self.state_code, '#6B7280')


class TelemetryReading(models.Model):
    """
    Immutable raw sensor reading pulse record.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='telemetry_readings')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    pulse_count = models.PositiveIntegerField(default=1)
    instant_cpm = models.FloatField(default=0.0)
    state_code = models.CharField(max_length=30, choices=STATE_CHOICES, default='RUNNING')
    vibration_rms = models.FloatField(default=0.8)
    temperature_c = models.FloatField(default=42.0)
    is_simulated = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.machine.code}: +{self.pulse_count} ({self.instant_cpm} CPM)"


class DowntimeEvent(models.Model):
    """
    Discrete machine state interval or downtime stoppage.
    Maintains ISO 22400 time accounting and TPM Six Big Losses attribution.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='downtime_events')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='downtime_events')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    state_code = models.CharField(max_length=30, choices=STATE_CHOICES, default='UNPLANNED_DOWNTIME')
    
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    # Classification & Taxonomies
    tpm_loss_type = models.CharField(max_length=50, choices=TPM_LOSS_CHOICES, null=True, blank=True)
    category = models.ForeignKey(ReasonCategory, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.ForeignKey(StoppageReason, on_delete=models.SET_NULL, null=True, blank=True)
    is_planned = models.BooleanField(default=False)
    is_classified = models.BooleanField(default=False)
    classified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    is_simulated = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        status = f" ({self.duration_seconds}s)" if self.end_time else " [ACTIVE]"
        return f"{self.machine.code} - {self.state_code}{status}"

    @property
    def is_active(self):
        return self.end_time is None

    def close_interval(self, close_time=None):
        """Closes an active downtime interval and calculates final duration in seconds."""
        if not self.end_time:
            self.end_time = close_time or timezone.now()
            duration = int((self.end_time - self.start_time).total_seconds())
            self.duration_seconds = max(0, duration)
            self.save(update_fields=['end_time', 'duration_seconds'])


class SimulationScenarioState(models.Model):
    """
    Simulation controller settings and state tracking per production line.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='simulation_controllers')
    active_scenario = models.CharField(max_length=50, choices=SCENARIO_CHOICES, default='NONE')
    clock_multiplier = models.FloatField(default=1.0)
    is_running = models.BooleanField(default=True)
    tick_count = models.PositiveIntegerField(default=0)
    scenario_started_at = models.DateTimeField(null=True, blank=True)
    last_tick_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['line__code']

    def __str__(self):
        return f"Simulator [{self.line.code}]: {self.active_scenario} @ {self.clock_multiplier}x"

