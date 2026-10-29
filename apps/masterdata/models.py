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

    class Meta:
        ordering = ['sequence_order', 'code']
        unique_together = ('line', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' and self.name_ar else self.name


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
