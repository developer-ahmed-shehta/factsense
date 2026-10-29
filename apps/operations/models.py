"""
Data Models for FactSense Shop-Floor Operations, Maintenance & Handovers.
Strictly implements:
- F05: Operator Touch Console logging (Scrap, Weight, Stoppage Classification & Splitting)
- F06: Stoppages & SMED 4-Phase Changeover Tracking
- F15: Live Floor Matrix & Guided Shift Handover
- F16: Maintenance Kanban Lifecycle, Repair Clock-in, Spares & Force-Lockout
"""

import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.masterdata.models import Factory, Line, Machine, Shift, Product, ReasonCategory, StoppageReason, DefectReason
from apps.telemetry.models import DowntimeEvent


class MaintenanceTicket(models.Model):
    """
    5-Stage Kanban Maintenance Incident & Repair Lifecycle.
    Enforces machine force-lockout workflow and technician clock-in timestamps.
    """
    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent Breakdown (Line Stopped)'),
    ]

    STATUS_CHOICES = [
        ('OPEN', 'Open / Unassigned'),
        ('ASSIGNED', 'Assigned / Dispatched'),
        ('IN_PROGRESS', 'In Progress / Under Repair'),
        ('WAITING_SPARES', 'Waiting for Spare Parts'),
        ('TESTING', 'Testing & Verification'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed / Verified'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=32, unique=True, db_index=True)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='maintenance_tickets')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='maintenance_tickets')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_tickets')
    downtime_event = models.ForeignKey(
        DowntimeEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_tickets'
    )

    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='HIGH')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='OPEN', db_index=True)

    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_tickets')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')

    # Security & Operational Lock
    force_lockout = models.BooleanField(
        default=True,
        help_text="If True, machine is locked out and operator touch console cannot produce until released."
    )
    is_operator_call = models.BooleanField(default=False, help_text="Triggered directly from Operator Kiosk 'Call Maintenance'")

    # Timestamps & SLA
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    work_started_at = models.DateTimeField(null=True, blank=True, help_text="Technician repair clock-in timestamp")
    waiting_spares_started_at = models.DateTimeField(null=True, blank=True)
    paused_sla_seconds = models.PositiveIntegerField(default=0)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Resolution & Audit (Mandatory before machine release)
    root_cause_category = models.ForeignKey(ReasonCategory, on_delete=models.SET_NULL, null=True, blank=True)
    root_cause_reason = models.ForeignKey(StoppageReason, on_delete=models.SET_NULL, null=True, blank=True)
    root_cause_notes = models.TextField(blank=True, help_text="Mandatory root cause details before release")
    solution_notes = models.TextField(blank=True, help_text="Mandatory technician repair actions performed")
    parts_used_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_number} - {self.machine.code} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            hex_part = uuid.uuid4().hex[:6].upper()
            year = timezone.now().year
            self.ticket_number = f"TKT-{year}-{hex_part}"
        super().save(*args, **kwargs)

    @property
    def elapsed_minutes(self):
        end = self.resolved_at or timezone.now()
        start = self.work_started_at or self.created_at
        return max(0, int((end - start).total_seconds() / 60))

    @property
    def is_locked(self):
        """Active lock condition: status is not RESOLVED or CLOSED, and force_lockout is True."""
        return self.force_lockout and self.status not in ['RESOLVED', 'CLOSED']


class SparePart(models.Model):
    """
    Spare parts inventory catalog for maintenance repairs.
    """
    CATEGORY_CHOICES = [
        ('MECHANICAL', 'Mechanical / Drive / Bearings'),
        ('ELECTRICAL', 'Electrical / Sensors / PLC'),
        ('PNEUMATIC', 'Pneumatic / Valves / Cylinders'),
        ('TOOLING', 'Tooling / Chucks / Guides'),
        ('CONSUMABLE', 'Consumables / Lubricants / Seals'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, related_name='spare_parts', null=True, blank=True)
    part_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='MECHANICAL')
    in_stock_quantity = models.PositiveIntegerField(default=10)
    min_stock_level = models.PositiveIntegerField(default=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))
    storage_location = models.CharField(max_length=50, default='Bin A-01')

    class Meta:
        ordering = ['part_number']

    def __str__(self):
        return f"{self.part_number} - {self.name} (Qty: {self.in_stock_quantity})"

    @property
    def is_low_stock(self):
        return self.in_stock_quantity <= self.min_stock_level


class SparePartRequisition(models.Model):
    """
    Requisition of a spare part for an active maintenance ticket.
    Transitions ticket to WAITING_SPARES and pauses SLA timer.
    """
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested (Waiting Spares)'),
        ('ISSUED', 'Issued / Delivered to Machine'),
        ('CANCELLED', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(MaintenanceTicket, on_delete=models.CASCADE, related_name='spare_requisitions')
    part = models.ForeignKey(SparePart, on_delete=models.CASCADE, related_name='requisitions')
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.ticket.ticket_number}: {self.quantity}x {self.part.part_number} [{self.status}]"


class ChangeoverEvent(models.Model):
    """
    Digital SMED (Single-Minute Exchange of Die) 4-Phase Changeover Tracker.
    Implements Shigeo Shingo 4-phase methodology:
    1. Line Clearance & CIP (Cleaning in Place)
    2. Mechanical Tooling Change (Chucks, starwheels, guides)
    3. Recipe & Parameter Loading (Digital setpoints)
    4. Test Run & Speed Ramp-Up (Ramp-up scrap tracking)
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'Changeover In Progress'),
        ('COMPLETED', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='changeovers')
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='changeovers')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    from_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='changeovers_from')
    to_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='changeovers_to')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')

    current_phase = models.PositiveIntegerField(
        default=1,
        choices=[
            (1, 'Phase 1: Line Clearance & CIP'),
            (2, 'Phase 2: Mechanical Tooling Swap'),
            (3, 'Phase 3: Digital Recipe Loading'),
            (4, 'Phase 4: Test Run & Ramp-Up to Speed'),
        ]
    )

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Phase Timers (Durations in seconds)
    phase1_started_at = models.DateTimeField(null=True, blank=True)
    phase1_duration_seconds = models.PositiveIntegerField(default=0)
    phase1_target_minutes = models.PositiveIntegerField(default=10)

    phase2_started_at = models.DateTimeField(null=True, blank=True)
    phase2_duration_seconds = models.PositiveIntegerField(default=0)
    phase2_target_minutes = models.PositiveIntegerField(default=15)

    phase3_started_at = models.DateTimeField(null=True, blank=True)
    phase3_duration_seconds = models.PositiveIntegerField(default=0)
    phase3_target_minutes = models.PositiveIntegerField(default=5)

    phase4_started_at = models.DateTimeField(null=True, blank=True)
    phase4_duration_seconds = models.PositiveIntegerField(default=0)
    phase4_target_minutes = models.PositiveIntegerField(default=10)

    total_duration_seconds = models.PositiveIntegerField(default=0)
    target_duration_minutes = models.PositiveIntegerField(default=40)

    rampup_total_units = models.PositiveIntegerField(default=0)
    rampup_scrap_units = models.PositiveIntegerField(default=0)

    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        to_sku = self.to_product.code if self.to_product else 'N/A'
        return f"{self.line.code} Changeover -> {to_sku} [Phase {self.current_phase}]"

    @property
    def total_duration_minutes(self):
        return round(self.total_duration_seconds / 60.0, 1)

    @property
    def variance_minutes(self):
        """Positive means exceeded target (overtime); negative means faster than target."""
        return round(self.total_duration_minutes - self.target_duration_minutes, 1)


class DefectLog(models.Model):
    """
    Shop-floor scrap defect entry recorded from Operator Touch Console numpad.
    """
    DISPOSITION_CHOICES = [
        ('SCRAP', 'Direct Scrap / Reject Bin'),
        ('REWORK', 'Rework Required'),
        ('QUARANTINE', 'Quality Quarantine Hold'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='defect_logs')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='defect_logs')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.ForeignKey(DefectReason, on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    disposition = models.CharField(max_length=20, choices=DISPOSITION_CHOICES, default='SCRAP')
    logged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        r_name = self.reason.name if self.reason else 'General Scrap'
        return f"{self.machine.code}: {self.quantity}x {r_name} ({self.disposition})"

    @property
    def quantity_pieces(self):
        return self.quantity

    @property
    def operator(self):
        return self.logged_by

    @property
    def financial_cost(self):
        unit_cost = self.product.scrap_cost if (self.product and self.product.scrap_cost) else Decimal('0.80')
        return self.quantity * unit_cost


class WeightSample(models.Model):
    """
    Checkweigher or manual scale sample weight entry (in grams) for live SPC monitoring.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='weight_samples')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='weight_samples')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='weight_samples')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)

    measured_weight_grams = models.DecimalField(max_digits=8, decimal_places=2)
    nominal_target_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('500.00'))
    deviation_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    is_within_spec = models.BooleanField(default=True)

    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.machine.code}: {self.measured_weight_grams}g (Dev: {self.deviation_grams:+.2f}g)"

    def save(self, *args, **kwargs):
        if self.product:
            self.nominal_target_grams = self.product.nominal_weight
            self.deviation_grams = self.measured_weight_grams - self.nominal_target_grams
            self.is_within_spec = (self.product.lsl_weight <= self.measured_weight_grams <= self.product.usl_weight)
        super().save(*args, **kwargs)


class ShiftHandover(models.Model):
    """
    Official 3-Step Shift Handover document.
    Step 1: Shift Metrics Review (Output, Scrap, Downtime).
    Step 2: Open Issues & Maintenance Tickets acknowledgment.
    Step 3: Outgoing & Incoming Operator / Supervisor digital sign-off and shift lock.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'In Progress Draft'),
        ('SUBMITTED', 'Submitted for Review'),
        ('LOCKED', 'Signed & Locked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='handovers')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='handovers')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    outgoing_supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='outgoing_handovers')
    incoming_supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming_handovers')

    # Shift Performance Summary
    total_output_units = models.PositiveIntegerField(default=0)
    total_scrap_units = models.PositiveIntegerField(default=0)
    total_downtime_minutes = models.PositiveIntegerField(default=0)
    open_tickets_count = models.PositiveIntegerField(default=0)
    shift_oee = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))

    # Remarks & Carried-over Context
    production_summary = models.TextField(blank=True, help_text="General shift narrative and pacing remarks")
    safety_incidents = models.TextField(blank=True, default="Zero safety incidents reported during shift.")
    maintenance_handoff_notes = models.TextField(blank=True, help_text="Equipment condition and open repairs to monitor")
    quality_handoff_notes = models.TextField(blank=True, help_text="Defects, scrap reasons, and weight sampling trends")

    created_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.line.code} - {self.shift.name} ({self.date}) [{self.get_status_display()}]"
