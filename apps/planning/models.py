"""
Planning, Work Order Central Dispatch, Stage Routing, Material Staging,
and ERP / Odoo Synchronization Models.
Fulfills F18 and Batch 6 specifications.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.masterdata.models import Product, Line, Machine, Process, Shift


class WorkOrder(models.Model):
    """
    Central production work order tracking product, line, planned schedule,
    lot traceability, and real-time execution status.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PLANNED', 'Planned'),
        ('RELEASED', 'Released to Floor'),
        ('IN_PROGRESS', 'In Progress'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('SHORT_CLOSED', 'Short-Closed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=64, unique=True, db_index=True)
    external_erp_id = models.CharField(max_length=64, blank=True, db_index=True, help_text='Odoo MO or ERP external ID')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='work_orders')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='work_orders')
    target_quantity = models.PositiveIntegerField(default=1000)
    produced_quantity = models.PositiveIntegerField(default=0)
    scrap_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='PLANNED', choices=STATUS_CHOICES)
    priority = models.CharField(max_length=20, default='NORMAL', choices=PRIORITY_CHOICES)
    
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    lot_number = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    short_close_reason = models.CharField(max_length=255, blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_work_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-planned_start', '-created_at']
        verbose_name = 'Work Order'
        verbose_name_plural = 'Work Orders'

    def __str__(self):
        return f"{self.order_number} - {self.product.code} ({self.status})"

    @property
    def progress_percent(self):
        if not self.target_quantity:
            return 0.0
        return min(100.0, round((self.produced_quantity / self.target_quantity) * 100, 1))

    @property
    def remaining_quantity(self):
        return max(0, self.target_quantity - self.produced_quantity)

    @property
    def good_pieces(self):
        return max(0, self.produced_quantity - self.scrap_quantity)

    @property
    def is_active(self):
        return self.status in ['RELEASED', 'IN_PROGRESS']

    @property
    def can_release(self):
        return self.status in ['DRAFT', 'PLANNED']

    @property
    def can_start(self):
        return self.status == 'RELEASED'

    @property
    def can_pause(self):
        return self.status == 'IN_PROGRESS'

    @property
    def can_resume(self):
        return self.status == 'PAUSED'

    @property
    def can_complete(self):
        return self.status in ['IN_PROGRESS', 'PAUSED']

    @property
    def can_short_close(self):
        return self.status in ['RELEASED', 'IN_PROGRESS', 'PAUSED']


class WorkOrderRoutingStage(models.Model):
    """
    Sequential manufacturing process stages for a Work Order
    (e.g., Blow Molding -> Rinsing -> Filling -> Capping -> Labeling -> Packing).
    """
    STAGE_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('BLOCKED', 'Blocked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='stages')
    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name='work_order_stages')
    sequence_order = models.PositiveIntegerField(default=1)
    target_quantity = models.PositiveIntegerField(default=0)
    completed_quantity = models.PositiveIntegerField(default=0)
    scrap_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='PENDING', choices=STAGE_STATUS_CHOICES)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['work_order', 'sequence_order']
        unique_together = ('work_order', 'sequence_order')

    def __str__(self):
        return f"{self.work_order.order_number} - Step {self.sequence_order}: {self.process.name} ({self.status})"

    @property
    def progress_percent(self):
        if not self.target_quantity:
            return 0.0
        return min(100.0, round((self.completed_quantity / self.target_quantity) * 100, 1))


class MachineShiftAssignment(models.Model):
    """
    Production assignment calendar allocating a Work Order to a Line/Machine and Shift.
    """
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='shift_assignments')
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='work_order_assignments')
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='work_order_assignments')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='work_order_assignments')
    scheduled_date = models.DateField(db_index=True)
    planned_target_units = models.PositiveIntegerField(default=1000)
    actual_produced_units = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='SCHEDULED', choices=STATUS_CHOICES)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_date', 'shift__sequence']

    def __str__(self):
        return f"{self.work_order.order_number} -> {self.line.code} [{self.shift.name}] ({self.scheduled_date})"


class WorkOrderMaterial(models.Model):
    """
    Bill of Materials (BOM) staging items required for executing a work order
    (e.g., Preforms, Caps, Labels, Packaging boxes).
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Staging'),
        ('PARTIALLY_STAGED', 'Partially Staged'),
        ('STAGED', 'Fully Staged'),
        ('SHORTAGE', 'Material Shortage'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='materials')
    material_code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    required_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    staged_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    unit_of_measure = models.CharField(max_length=20, default='PCS')
    lot_number = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, default='PENDING', choices=STATUS_CHOICES)
    staged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staged_materials'
    )
    staged_at = models.DateTimeField(null=True, blank=True)
    shortage_notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['work_order', 'material_code']

    def __str__(self):
        return f"{self.material_code} - {self.name} for {self.work_order.order_number}"

    @property
    def staged_percent(self):
        if not self.required_quantity or self.required_quantity <= 0:
            return 0.0
        return min(100.0, round(float(self.staged_quantity) / float(self.required_quantity) * 100, 1))

    @property
    def is_fully_staged(self):
        return self.staged_quantity >= self.required_quantity


class MaterialDelivery(models.Model):
    """
    Inbound raw material delivery receipt linked to production readiness.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_number = models.CharField(max_length=64, unique=True)
    supplier = models.CharField(max_length=150)
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries'
    )
    material_code = models.CharField(max_length=50)
    material_name = models.CharField(max_length=150, blank=True)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2)
    unit_of_measure = models.CharField(max_length=20, default='PCS')
    lot_number = models.CharField(max_length=64)
    dock_location = models.CharField(max_length=50, default='Dock-A (Raw Goods)')
    received_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"{self.delivery_number} - {self.material_code} ({self.quantity_received} {self.unit_of_measure})"


class ERPSyncRun(models.Model):
    """
    Ledger of ERP / Odoo synchronization cycles with status, idempotency, and counters.
    """
    DIRECTION_CHOICES = [
        ('INBOUND_IMPORT', 'Inbound Import (ERP -> MES)'),
        ('OUTBOUND_EXPORT', 'Outbound Feedback (MES -> ERP)'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partial with Conflicts'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_id = models.CharField(max_length=64, unique=True, db_index=True)
    direction = models.CharField(max_length=20, default='INBOUND_IMPORT', choices=DIRECTION_CHOICES)
    system_source = models.CharField(max_length=50, default='Odoo 17 ERP (MRP)')
    status = models.CharField(max_length=20, default='SUCCESS', choices=STATUS_CHOICES)
    records_total = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_conflicted = models.PositiveIntegerField(default=0)
    retry_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    log_summary = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.run_id} - {self.direction} [{self.status}]"


class ERPSyncConflict(models.Model):
    """
    Conflict queue item when upstream ERP data mismatches active shop-floor reality.
    Enforces explicit review before overwriting production facts.
    """
    CONFLICT_TYPE_CHOICES = [
        ('QUANTITY_DISCREPANCY', 'Target Quantity Mismatch'),
        ('STATUS_MISMATCH', 'Status Conflict'),
        ('DATE_CONFLICT', 'Schedule Window Mismatch'),
        ('CANCELLED_UPSTREAM', 'Order Cancelled Upstream in ERP'),
        ('DUPLICATE_LOT', 'Lot Number Conflict'),
    ]

    RESOLUTION_CHOICES = [
        ('UNRESOLVED', 'Unresolved / Pending Review'),
        ('ACCEPTED_REMOTE', 'Accepted Remote (ERP Overwrote MES)'),
        ('KEPT_LOCAL', 'Kept Local (MES Preserved)'),
        ('DISMISSED', 'Dismissed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_run = models.ForeignKey(ERPSyncRun, on_delete=models.CASCADE, related_name='conflicts')
    external_erp_id = models.CharField(max_length=64, db_index=True)
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='erp_conflicts'
    )
    conflict_type = models.CharField(max_length=30, default='QUANTITY_DISCREPANCY', choices=CONFLICT_TYPE_CHOICES)
    field_name = models.CharField(max_length=50, default='target_quantity')
    local_value = models.CharField(max_length=255)
    remote_value = models.CharField(max_length=255)
    resolution = models.CharField(max_length=20, default='UNRESOLVED', choices=RESOLUTION_CHOICES)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Conflict on {self.external_erp_id} ({self.conflict_type}): {self.resolution}"

