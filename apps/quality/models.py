"""
Quality Assurance, Statistical Process Control (SPC) & Product Giveaway Models.
Strictly implements:
- ISO 22400-2 Statistical Process Control (X-bar and R control charts)
- Subgroup sampling (subgroup size n=5)
- Specification limits (USL, LSL, Nominal)
- Process capability indices (Cp, Cpk)
- Overfill giveaway costing and raw material savings
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.masterdata.models import Line, Machine, Product, Shift


class SPCConfig(models.Model):
    """
    Quality and SPC parameters per product and machine.
    Defines specification limits (USL, LSL, Nominal) and financial unit costs.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='spc_configs')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, null=True, blank=True, related_name='spc_configs')
    
    # Specification Limits (grams)
    nominal_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('500.00'),
                                        help_text="Target nominal fill weight in grams.")
    usl_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('505.00'),
                                    help_text="Upper Specification Limit in grams.")
    lsl_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('495.00'),
                                    help_text="Lower Specification Limit (Legal minimum underfill limit) in grams.")
    
    # Sampling parameters
    subgroup_size = models.PositiveSmallIntegerField(default=5, help_text="Number of samples per subgroup (typically 5).")
    
    # Financial assumptions
    material_cost_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('18.50'),
                                               help_text="Raw material cost per kilogram for giveaway loss valuation.")
    annual_production_units = models.PositiveIntegerField(default=12000000,
                                                          help_text="Projected annual output units for annual savings simulation.")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product', 'machine']
        verbose_name = 'SPC Configuration'
        verbose_name_plural = 'SPC Configurations'

    def __str__(self):
        m_code = self.machine.code if self.machine else 'All Machines'
        return f"{self.product.name} ({m_code}): Nominal={self.nominal_grams}g [LSL={self.lsl_grams}, USL={self.usl_grams}]"


class QualitySubgroup(models.Model):
    """
    Statistical subgroup of n continuous samples (ISO 22400-2).
    Holds subgroup mean (X-bar), range (R), and standard deviation (s).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(SPCConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name='subgroups')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='quality_subgroups')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='quality_subgroups')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='quality_subgroups')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    
    subgroup_number = models.PositiveIntegerField(default=1)
    sample_mean = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'),
                                      help_text="Subgroup average weight (X-bar)")
    sample_range = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'),
                                       help_text="Subgroup range (R = max - min)")
    sample_std = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'),
                                     help_text="Subgroup sample standard deviation (s)")
    
    is_out_of_control = models.BooleanField(default=False)
    out_of_control_reason = models.CharField(max_length=200, blank=True)
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)
    is_simulated = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Quality Subgroup'
        verbose_name_plural = 'Quality Subgroups'

    def __str__(self):
        return f"Subgroup #{self.subgroup_number} - {self.machine.code}: Mean={self.sample_mean}g, R={self.sample_range}g"


class QualitySample(models.Model):
    """
    Discrete weight sample reading in grams.
    Belongs optionally to a QualitySubgroup.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subgroup = models.ForeignKey(QualitySubgroup, on_delete=models.CASCADE, null=True, blank=True, related_name='samples')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='quality_samples')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='quality_samples')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='quality_samples')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    
    measured_weight_grams = models.DecimalField(max_digits=8, decimal_places=2)
    nominal_target_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('500.00'))
    deviation_grams = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    is_within_spec = models.BooleanField(default=True)
    
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    is_simulated = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Quality Sample'
        verbose_name_plural = 'Quality Samples'

    def __str__(self):
        return f"{self.machine.code}: {self.measured_weight_grams}g (Dev: {self.deviation_grams:+.2f}g)"

    def save(self, *args, **kwargs):
        if self.nominal_target_grams and self.measured_weight_grams is not None:
            self.deviation_grams = self.measured_weight_grams - self.nominal_target_grams
        super().save(*args, **kwargs)

