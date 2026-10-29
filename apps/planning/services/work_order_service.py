"""
Work Order Lifecycle, Stage Routing, and Material Staging Service.
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.masterdata.models import Product, Line, Machine, Process, Shift
from apps.planning.models import (
    WorkOrder, WorkOrderRoutingStage, MachineShiftAssignment,
    WorkOrderMaterial, MaterialDelivery
)


DEFAULT_BOTTLING_STAGES = [
    ('BLOW_MOLDING', 'Blow Molding / Preform Inflation', 1),
    ('RINSING_FILLING', 'Rotary Rinsing & Filling', 2),
    ('CAPPING', 'Rotary Chuck Capping', 3),
    ('LABELING', 'Roll-Fed Labeling', 4),
    ('CASE_PACKING', 'Shrink Film Case Packing', 5),
    ('PALLETIZING', 'Robotic Palletizing', 6),
]


def create_work_order(
    order_number,
    product_id,
    line_id,
    target_quantity,
    planned_start,
    planned_end,
    priority='NORMAL',
    lot_number='',
    notes='',
    external_erp_id='',
    created_by=None
):
    """
    Creates a new WorkOrder with routing stages and Bill of Materials staging items.
    """
    product = Product.objects.get(id=product_id)
    line = Line.objects.get(id=line_id)

    if not lot_number:
        today_str = timezone.now().strftime('%Y%m%d')
        lot_number = f"LOT-{product.code}-{today_str}"

    with transaction.atomic():
        order = WorkOrder.objects.create(
            order_number=order_number,
            external_erp_id=external_erp_id,
            product=product,
            line=line,
            target_quantity=int(target_quantity),
            priority=priority,
            planned_start=planned_start,
            planned_end=planned_end,
            lot_number=lot_number,
            notes=notes,
            created_by=created_by,
            status='PLANNED'
        )

        # 1. Initialize Routing Stages
        # If product has explicit processes linked, use them; otherwise use default bottling stages
        product_processes = list(product.processes.all().order_by('sequence_order'))
        if product_processes:
            for seq, proc in enumerate(product_processes, start=1):
                WorkOrderRoutingStage.objects.create(
                    work_order=order,
                    process=proc,
                    sequence_order=seq,
                    target_quantity=order.target_quantity,
                    status='PENDING'
                )
        else:
            for code, name, seq in DEFAULT_BOTTLING_STAGES:
                proc, _ = Process.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'sequence_order': seq}
                )
                WorkOrderRoutingStage.objects.create(
                    work_order=order,
                    process=proc,
                    sequence_order=seq,
                    target_quantity=order.target_quantity,
                    status='PENDING'
                )

        # 2. Initialize Material Staging Items
        target_dec = Decimal(str(order.target_quantity))
        materials_data = [
            (f"PREFORM-{product.code}", f"{product.name} PET Preforms", target_dec, 'PCS'),
            (f"CAP-{product.code}", "28mm Tamper-Evident Caps", target_dec, 'PCS'),
            (f"LABEL-{product.code}", "Roll-Fed OPP Bottle Labels", target_dec, 'PCS'),
            (f"FILM-{product.code}", "LDPE Heat-Shrink Wrapping Film", Decimal(str(round(float(target_dec) / 24.0, 1))), 'Rolls'),
        ]
        for m_code, m_name, req_qty, uom in materials_data:
            WorkOrderMaterial.objects.create(
                work_order=order,
                material_code=m_code,
                name=m_name,
                required_quantity=req_qty,
                staged_quantity=Decimal('0.0'),
                unit_of_measure=uom,
                status='PENDING'
            )

    return order


def release_work_order(work_order, user=None):
    """
    Releases a PLANNED or DRAFT work order to the shop floor.
    """
    if work_order.status not in ['DRAFT', 'PLANNED']:
        raise ValueError(f"Cannot release order in status {work_order.status}")
    work_order.status = 'RELEASED'
    work_order.save(update_fields=['status', 'updated_at'])
    return work_order


def start_work_order(work_order, user=None):
    """
    Starts an active work order, sets Line active product, and activates the first process stage.
    """
    if work_order.status != 'RELEASED':
        raise ValueError(f"Cannot start order in status {work_order.status}. Must be RELEASED.")
    
    with transaction.atomic():
        work_order.status = 'IN_PROGRESS'
        if not work_order.actual_start:
            work_order.actual_start = timezone.now()
        work_order.save(update_fields=['status', 'actual_start', 'updated_at'])

        # Set line active SKU
        work_order.line.current_product = work_order.product
        work_order.line.save(update_fields=['current_product'])

        # Activate first stage
        first_stage = work_order.stages.order_by('sequence_order').first()
        if first_stage and first_stage.status == 'PENDING':
            first_stage.status = 'IN_PROGRESS'
            first_stage.started_at = timezone.now()
            first_stage.save(update_fields=['status', 'started_at'])

    return work_order


def pause_work_order(work_order, user=None):
    """Pauses an in-progress work order."""
    if work_order.status != 'IN_PROGRESS':
        raise ValueError("Only IN_PROGRESS orders can be paused.")
    work_order.status = 'PAUSED'
    work_order.save(update_fields=['status', 'updated_at'])
    return work_order


def resume_work_order(work_order, user=None):
    """Resumes a paused work order."""
    if work_order.status != 'PAUSED':
        raise ValueError("Only PAUSED orders can be resumed.")
    work_order.status = 'IN_PROGRESS'
    work_order.save(update_fields=['status', 'updated_at'])
    return work_order


def complete_work_order(work_order, user=None):
    """
    Marks an order as COMPLETED and finishes all stages.
    """
    if work_order.status not in ['IN_PROGRESS', 'PAUSED', 'RELEASED']:
        raise ValueError(f"Cannot complete order in status {work_order.status}")

    with transaction.atomic():
        now = timezone.now()
        work_order.status = 'COMPLETED'
        work_order.actual_end = now
        if not work_order.actual_start:
            work_order.actual_start = now
        # Default produced quantity to target if not set
        if work_order.produced_quantity == 0:
            work_order.produced_quantity = work_order.target_quantity
        work_order.save(update_fields=['status', 'actual_start', 'actual_end', 'produced_quantity', 'updated_at'])

        # Complete all stages
        for stage in work_order.stages.all():
            if stage.status != 'COMPLETED':
                stage.status = 'COMPLETED'
                if not stage.completed_at:
                    stage.completed_at = now
                if stage.completed_quantity == 0:
                    stage.completed_quantity = stage.target_quantity
                stage.save(update_fields=['status', 'completed_at', 'completed_quantity'])

    return work_order


def short_close_work_order(work_order, reason, user=None):
    """
    Short-closes an order with a mandatory justification reason.
    """
    if not reason or not reason.strip():
        raise ValueError("A valid justification reason is mandatory to short-close an order.")
    
    work_order.status = 'SHORT_CLOSED'
    work_order.short_close_reason = reason.strip()
    work_order.actual_end = timezone.now()
    work_order.save(update_fields=['status', 'short_close_reason', 'actual_end', 'updated_at'])
    return work_order


def record_stage_progress(stage, completed_units, scrap_units=0):
    """
    Records completed output for a routing stage and auto-advances the next stage.
    """
    with transaction.atomic():
        stage.completed_quantity += int(completed_units)
        stage.scrap_quantity += int(scrap_units)
        if stage.status == 'PENDING':
            stage.status = 'IN_PROGRESS'
            stage.started_at = timezone.now()

        if stage.completed_quantity >= stage.target_quantity:
            stage.status = 'COMPLETED'
            stage.completed_at = timezone.now()

        stage.save()

        # Update parent work order produced units if this is the final stage
        total_stages = stage.work_order.stages.count()
        if stage.sequence_order == total_stages:
            stage.work_order.produced_quantity = stage.completed_quantity
            stage.work_order.scrap_quantity += int(scrap_units)
            stage.work_order.save(update_fields=['produced_quantity', 'scrap_quantity', 'updated_at'])

        # If completed, advance next stage
        if stage.status == 'COMPLETED':
            next_stage = stage.work_order.stages.filter(sequence_order=stage.sequence_order + 1).first()
            if next_stage and next_stage.status == 'PENDING':
                next_stage.status = 'IN_PROGRESS'
                next_stage.started_at = timezone.now()
                next_stage.save(update_fields=['status', 'started_at'])

    return stage


def stage_material(material, staged_qty, lot_number='', user=None):
    """
    Records material staging for a work order and updates staging status.
    """
    staged_dec = Decimal(str(staged_qty))
    material.staged_quantity += staged_dec
    if lot_number:
        material.lot_number = lot_number
    material.staged_by = user
    material.staged_at = timezone.now()

    if material.staged_quantity >= material.required_quantity:
        material.status = 'STAGED'
    else:
        material.status = 'PARTIALLY_STAGED'

    material.save()
    return material


def flag_material_shortage(material, shortage_notes='', user=None):
    """
    Flags a raw material shortage condition on an active work order.
    """
    material.status = 'SHORTAGE'
    material.shortage_notes = shortage_notes or "Raw material delivery shortage flagged by staging supervisor"
    material.save(update_fields=['status', 'shortage_notes'])
    return material


def assign_shift_schedule(work_order, shift, scheduled_date, target_units, machine=None, notes='', user=None):
    """
    Schedules an allocation of a Work Order to a Shift calendar slot.
    """
    assignment, created = MachineShiftAssignment.objects.update_or_create(
        work_order=work_order,
        shift=shift,
        scheduled_date=scheduled_date,
        defaults={
            'line': work_order.line,
            'machine': machine or work_order.line.bottleneck_machine,
            'planned_target_units': int(target_units),
            'notes': notes,
            'assigned_by': user,
            'status': 'SCHEDULED',
        }
    )
    return assignment

