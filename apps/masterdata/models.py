import uuid
from django.db import models


class Factory(models.Model):
    """
    Top-level manufacturing site / plant entity.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    industry = models.CharField(max_length=100, default='Food & Beverage')
    timezone = models.CharField(max_length=50, default='UTC')
    currency = models.CharField(max_length=10, default='EGP')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Factories"
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class Line(models.Model):
    """
    Production line within a factory.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, related_name='lines')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    sequence = models.PositiveIntegerField(default=1)
    target_oee = models.FloatField(default=85.0)
    bottleneck_machine = models.ForeignKey(
        'Machine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bottleneck_for_line'
    )
    current_product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_on_lines'
    )

    class Meta:
        ordering = ['sequence', 'code']
        unique_together = ('factory', 'code')

    def __str__(self):
        return f"{self.name} [{self.factory.code}]"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class Machine(models.Model):
    """
    Industrial asset on a production line.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='machines')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    category = models.CharField(
        max_length=50,
        default='FILLER',
        choices=[
            ('BLOW_MOLDER', 'Blow Molder'),
            ('RINSER', 'Rinser'),
            ('FILLER', 'Filler'),
            ('CAPPER', 'Capper'),
            ('LABELER', 'Labeler'),
            ('PACKER', 'Case Packer'),
            ('PALLETIZER', 'Palletizer'),
            ('CONVEYOR', 'Conveyor'),
            ('SEALER', 'Sealer'),
            ('INSPECTION', 'Inspection'),
            ('OTHER', 'Other Equipment'),
        ]
    )
    sequence_order = models.PositiveIntegerField(default=10)
    criticality_rank = models.CharField(
        max_length=1,
        default='A',
        choices=[('A', 'A - Critical / Bottleneck'), ('B', 'B - Major Machine'), ('C', 'C - Buffer / Secondary')]
    )
    ideal_run_rate_cpm = models.FloatField(default=120.0, help_text="Ideal nameplate rate in CPM (Units/min)")
    is_bottleneck = models.BooleanField(default=False)
    sensor_protocol = models.CharField(
        max_length=30,
        default='SIMULATED',
        choices=[
            ('GPIO_PULSE', 'GPIO Digital Pulse'),
            ('MODBUS_TCP', 'Modbus TCP / IP'),
            ('MQTT', 'MQTT Telemetry Broker'),
            ('OPC_UA', 'OPC-UA Server'),
            ('SIMULATED', 'Internal Virtual Simulator'),
        ]
    )
    sensor_ip = models.GenericIPAddressField(null=True, blank=True, help_text="Edge Gateway or Sensor IP")
    modbus_address = models.PositiveIntegerField(default=1, help_text="Modbus register / unit ID")
    pulse_pin = models.PositiveIntegerField(null=True, blank=True, help_text="PLC / GPIO input pin number")

    class Meta:
        ordering = ['sequence_order', 'code']
        unique_together = ('line', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name

    @property
    def ideal_cpm(self):
        return int(self.ideal_run_rate_cpm)


class Process(models.Model):
    """
    Standard production process step (e.g. Blow Molding, Filling, Capping).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence_order', 'code']
        verbose_name_plural = "Processes"

    def __str__(self):
        return self.name

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class Product(models.Model):
    """
    Product SKU / Recipe matching the reference Product Management specification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    code = models.CharField(max_length=50, unique=True, help_text="SKU Code, e.g. SKU-WTR-500")
    name = models.CharField(max_length=150, help_text="Product name in English")
    name_ar = models.CharField(max_length=150, blank=True, help_text="Product name in Arabic")
    category = models.CharField(max_length=100, default='Beverage')
    unit_of_measure = models.CharField(
        max_length=20,
        default='Bottle',
        choices=[
            ('Bottle', 'Bottle'),
            ('Can', 'Can'),
            ('Pack', 'Pack'),
            ('Carton', 'Carton'),
            ('KG', 'Kilogram'),
            ('Liter', 'Liter'),
        ]
    )
    sop_document_title = models.CharField(max_length=150, blank=True, default='SOP-STD-01.pdf')
    sop_document_url = models.CharField(max_length=255, blank=True, default='#')
    ideal_cycle_time_sec = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.50,
        help_text="Cycle time in seconds per unit"
    )
    rated_speed_cpm = models.PositiveIntegerField(
        default=120,
        help_text="Rated speed in units per minute (CPM)"
    )
    processes = models.ManyToManyField(Process, blank=True, related_name='products')
    
    # Quality & Financial Parameters
    nominal_weight = models.DecimalField(max_digits=8, decimal_places=2, default=500.0, help_text="Nominal fill weight/volume in g or ml")
    usl_weight = models.DecimalField(max_digits=8, decimal_places=2, default=505.0, help_text="Upper Specification Limit")
    lsl_weight = models.DecimalField(max_digits=8, decimal_places=2, default=495.0, help_text="Lower Specification Limit")
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2, default=2.50, help_text="Standard unit manufacturing cost")
    scrap_cost = models.DecimalField(max_digits=8, decimal_places=2, default=1.80, help_text="Loss cost per scrapped unit")

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name

    @property
    def sku(self):
        return self.code

    @property
    def cycle_time_display(self):
        return f"{self.ideal_cycle_time_sec:.2f} s ({self.rated_speed_cpm} CPM)"


class MachineProductRate(models.Model):
    """
    Machine x Product specific rated speed matrix.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='product_rates')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='machine_rates')
    rated_speed_cpm = models.FloatField(default=120.0)
    ideal_cycle_time_sec = models.FloatField(default=0.50)

    class Meta:
        unique_together = ('machine', 'product')

    def __str__(self):
        return f"{self.machine.code} x {self.product.code}: {self.rated_speed_cpm} CPM"


class Shift(models.Model):
    """
    Factory shift timing and planned duration.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, related_name='shifts')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    unpaid_break_minutes = models.PositiveIntegerField(default=30)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence', 'start_time']
        unique_together = ('factory', 'code')

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name

    @property
    def total_scheduled_minutes(self):
        from datetime import datetime, date
        dummy = date(2000, 1, 1)
        dt_start = datetime.combine(dummy, self.start_time)
        dt_end = datetime.combine(dummy, self.end_time)
        if dt_end <= dt_start:
            dt_end = datetime.combine(date(2000, 1, 2), self.end_time)
        return int((dt_end - dt_start).total_seconds() / 60)

    @property
    def planned_operating_minutes(self):
        total = self.total_scheduled_minutes
        if hasattr(self, 'breaks') and self.breaks.filter(is_unpaid=True).exists():
            unpaid = sum(b.duration_minutes for b in self.breaks.filter(is_unpaid=True))
        else:
            unpaid = self.unpaid_break_minutes or 0
        return max(0, total - unpaid)


class ReasonCategory(models.Model):
    """
    High-level category for stoppage reasons.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    department = models.CharField(
        max_length=50,
        default='OPERATIONS',
        choices=[
            ('MECHANICAL', 'Mechanical'),
            ('ELECTRICAL', 'Electrical'),
            ('OPERATIONS', 'Operations'),
            ('QUALITY', 'Quality'),
            ('SUPPLY_CHAIN', 'Supply Chain'),
            ('SAFETY', 'Safety'),
            ('UTILITIES', 'Utilities'),
        ]
    )
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name_plural = 'Reason Categories'
        ordering = ['sequence', 'name']

    def __str__(self):
        return f"{self.name} ({self.department})"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class StoppageReason(models.Model):
    """
    Discrete equipment stoppage reason mapped to TPM Six Big Losses.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ReasonCategory, on_delete=models.CASCADE, related_name='reasons')
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    tpm_loss_type = models.CharField(
        max_length=50,
        default='AVAILABILITY_BREAKDOWN',
        choices=[
            ('AVAILABILITY_BREAKDOWN', 'Breakdown Loss (Unplanned Downtime)'),
            ('AVAILABILITY_CHANGEOVER', 'Setup & Changeover Loss'),
            ('PERFORMANCE_MINOR_STOP', 'Minor Stoppages (< 5 min)'),
            ('PERFORMANCE_SPEED_LOSS', 'Reduced Speed Loss'),
            ('QUALITY_DEFECTS', 'Production Defect & Scrap Loss'),
            ('QUALITY_STARTUP_SCRAP', 'Startup Reject Loss'),
        ]
    )
    is_planned = models.BooleanField(default=False)
    force_logout = models.BooleanField(default=False, help_text='Force logout operator session during active lock')
    standard_resolution_min = models.PositiveIntegerField(default=15)

    class Meta:
        ordering = ['category__sequence', 'code']

    def __str__(self):
        return f"{self.name} [{self.code}]"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class DefectReason(models.Model):
    """
    Quality defect taxonomy classification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=100, default='Packaging')
    default_disposition = models.CharField(
        max_length=20,
        default='SCRAP',
        choices=[
            ('SCRAP', 'Scrap / Discard'),
            ('REWORK', 'Rework / Reprocess'),
            ('QUARANTINE', 'Quality Quarantine'),
        ]
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.name} [{self.code}]"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class PlannedBreak(models.Model):
    """
    Unpaid or paid break scheduled inside a shift.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='breaks')
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=15)
    is_unpaid = models.BooleanField(default=True, help_text='If True, deducted from planned production time')

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.name} ({self.duration_minutes}m)"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


class KioskDevice(models.Model):
    """
    Physical touch tablet device paired with an asset.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='kiosks')
    device_name = models.CharField(max_length=100)
    device_token = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    claim_code = models.CharField(max_length=16, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20,
        default='PENDING',
        choices=[
            ('ACTIVE', 'Active / Paired'),
            ('PENDING', 'Pending Claim'),
            ('LOCKED', 'Locked / Maintenance Hold'),
        ]
    )
    is_exclusive = models.BooleanField(default=True, help_text='Enforces one active operator session at any time')
    paired_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device_name} ({self.claim_code}) - {self.status}"
