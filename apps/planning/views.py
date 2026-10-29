"""
Planning, Work Order Dispatch, Shift Assignment Matrix, Material Staging,
and ERP / Odoo Synchronization Views.
Fulfills F18 and Batch 6 specifications.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from apps.accounts.decorators import role_required
from apps.masterdata.models import Line, Machine, Product, Shift, Process
from apps.planning.models import (
    WorkOrder, WorkOrderRoutingStage, MachineShiftAssignment,
    WorkOrderMaterial, MaterialDelivery, ERPSyncRun, ERPSyncConflict
)
from apps.planning.services import work_order_service, erp_service


@role_required('planner', 'supply_chain', 'manager', 'supervisor', 'admin')
def work_orders_dispatch_view(request):
    """
    Central Work Order Dispatch hub (/work-orders/).
    Shows active and scheduled work orders, filters by line and status,
    and provides execution lifecycle action triggers.
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    selected_status = request.GET.get('status')
    search_query = request.GET.get('q', '').strip()

    orders_qs = WorkOrder.objects.select_related('product', 'line', 'created_by').prefetch_related('stages', 'materials')

    if selected_line_id:
        orders_qs = orders_qs.filter(line_id=selected_line_id)
    if selected_status:
        orders_qs = orders_qs.filter(status=selected_status)
    if search_query:
        orders_qs = orders_qs.filter(order_number__icontains=search_query)

    # Metrics
    total_orders = orders_qs.count()
    active_orders = orders_qs.filter(status__in=['RELEASED', 'IN_PROGRESS']).count()
    completed_orders = orders_qs.filter(status='COMPLETED').count()
    short_closed_orders = orders_qs.filter(status='SHORT_CLOSED').count()

    products = Product.objects.filter(is_archived=False)

    context = {
        'page_title': 'Work Order Central Dispatch',
        'page_title_ar': 'إدارة أوامر العمل والتوزيع المركزي',
        'active_tab': 'dispatch',
        'orders': orders_qs,
        'lines': lines,
        'products': products,
        'selected_line_id': selected_line_id,
        'selected_status': selected_status,
        'search_query': search_query,
        'total_orders': total_orders,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'short_closed_orders': short_closed_orders,
    }
    return render(request, 'planning/work_orders_dispatch.html', context)


@role_required('planner', 'supply_chain', 'admin')
@require_POST
def work_order_create_view(request):
    """Creates a new WorkOrder with routing stages and BOM material requirements."""
    order_number = request.POST.get('order_number', '').strip()
    product_id = request.POST.get('product_id')
    line_id = request.POST.get('line_id')
    target_quantity = request.POST.get('target_quantity', '1000')
    priority = request.POST.get('priority', 'NORMAL')
    planned_start_str = request.POST.get('planned_start')
    planned_end_str = request.POST.get('planned_end')
    lot_number = request.POST.get('lot_number', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not order_number:
        # Auto-generate order number
        today_code = timezone.now().strftime('%Y%m%d')
        order_number = f"WO-{today_code}-{WorkOrder.objects.count() + 1:03d}"

    try:
        now = timezone.now()
        planned_start = datetime.fromisoformat(planned_start_str) if planned_start_str else now
        planned_end = datetime.fromisoformat(planned_end_str) if planned_end_str else now + timedelta(hours=8)
        if timezone.is_naive(planned_start):
            planned_start = timezone.make_aware(planned_start)
        if timezone.is_naive(planned_end):
            planned_end = timezone.make_aware(planned_end)

        wo = work_order_service.create_work_order(
            order_number=order_number,
            product_id=product_id,
            line_id=line_id,
            target_quantity=int(target_quantity),
            planned_start=planned_start,
            planned_end=planned_end,
            priority=priority,
            lot_number=lot_number,
            notes=notes,
            created_by=request.user
        )
        messages.success(request, f"Work Order {wo.order_number} created successfully with {wo.stages.count()} process stages.")
    except Exception as e:
        messages.error(request, f"Failed to create Work Order: {str(e)}")

    return redirect('work_orders_home')


@role_required('planner', 'supply_chain', 'supervisor', 'admin')
@require_POST
def work_order_action_view(request, order_id):
    """
    Executes a lifecycle state transition on a WorkOrder:
    release, start, pause, resume, complete, short_close, export_erp.
    """
    order = get_object_or_404(WorkOrder, id=order_id)
    action = request.POST.get('action')

    try:
        if action == 'release':
            work_order_service.release_work_order(order, user=request.user)
            messages.success(request, f"Work Order {order.order_number} released to floor.")
        elif action == 'start':
            work_order_service.start_work_order(order, user=request.user)
            messages.success(request, f"Work Order {order.order_number} started on {order.line.name}.")
        elif action == 'pause':
            work_order_service.pause_work_order(order, user=request.user)
            messages.warning(request, f"Work Order {order.order_number} paused.")
        elif action == 'resume':
            work_order_service.resume_work_order(order, user=request.user)
            messages.success(request, f"Work Order {order.order_number} resumed.")
        elif action == 'complete':
            work_order_service.complete_work_order(order, user=request.user)
            messages.success(request, f"Work Order {order.order_number} marked as COMPLETED.")
        elif action == 'short_close':
            reason = request.POST.get('short_close_reason', '')
            work_order_service.short_close_work_order(order, reason=reason, user=request.user)
            messages.warning(request, f"Work Order {order.order_number} short-closed. Reason: {reason}")
        elif action == 'export_erp':
            sync_run = erp_service.simulate_erp_push_feedback(order, user=request.user)
            messages.success(request, f"Production feedback for {order.order_number} exported to ERP (Run {sync_run.run_id}).")
        else:
            messages.error(request, f"Unknown action '{action}'.")
    except Exception as e:
        messages.error(request, f"Action '{action}' failed: {str(e)}")

    return redirect(request.META.get('HTTP_REFERER', 'work_orders_home'))


@role_required('planner', 'supply_chain', 'manager', 'supervisor', 'admin')
def work_order_detail_view(request, order_id):
    """
    Work Order detail view showing Bill of Operations routing stages,
    material staging checklist, and shift assignments.
    """
    order = get_object_or_404(WorkOrder.objects.select_related('product', 'line', 'created_by'), id=order_id)
    stages = order.stages.select_related('process').all()
    materials = order.materials.all()
    assignments = order.shift_assignments.select_related('shift', 'machine').all()
    conflicts = order.erp_conflicts.all()

    context = {
        'page_title': f"Work Order: {order.order_number}",
        'page_title_ar': f"تفاصيل أمر العمل: {order.order_number}",
        'order': order,
        'stages': stages,
        'materials': materials,
        'assignments': assignments,
        'conflicts': conflicts,
    }
    return render(request, 'planning/work_order_detail.html', context)


@role_required('planner', 'supply_chain', 'manager', 'supervisor', 'admin')
def work_orders_schedule_matrix_view(request):
    """
    Visual Machine x Shift Assignment Calendar Matrix (/work-orders/schedule/).
    Displays a 3-shift matrix across machines/lines with active assignments.
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    # Date handling (default today)
    date_str = request.GET.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.now().date()
    else:
        target_date = timezone.now().date()

    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    shifts = Shift.objects.filter(factory=line.factory).order_by('sequence') if line and line.factory else Shift.objects.all().order_by('sequence')
    machines = line.machines.all().order_by('sequence_order') if line else Machine.objects.none()

    assignments = MachineShiftAssignment.objects.filter(
        line=line,
        scheduled_date=target_date
    ).select_related('work_order', 'work_order__product', 'shift', 'machine')

    # Build matrix map: (machine_id, shift_id) -> assignment
    matrix_data = []
    assignment_map = {}
    for a in assignments:
        key = (str(a.machine_id) if a.machine_id else 'LINE', str(a.shift_id))
        assignment_map[key] = a

    for m in machines:
        shift_cells = []
        for s in shifts:
            cell_assignment = assignment_map.get((str(m.id), str(s.id))) or assignment_map.get(('LINE', str(s.id)))
            shift_cells.append({
                'shift': s,
                'assignment': cell_assignment,
            })
        matrix_data.append({
            'machine': m,
            'shift_cells': shift_cells,
        })

    # Available work orders for modal assignment
    available_orders = WorkOrder.objects.filter(
        status__in=['PLANNED', 'RELEASED', 'IN_PROGRESS']
    ).select_related('product')
    if line:
        available_orders = available_orders.filter(line=line)

    context = {
        'page_title': 'Production Schedule & Shift Matrix',
        'page_title_ar': 'جدول الإنتاج وتوزيع الورديات',
        'active_tab': 'schedule',
        'lines': lines,
        'selected_line': line,
        'target_date': target_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'shifts': shifts,
        'matrix_data': matrix_data,
        'available_orders': available_orders,
        'machines': machines,
    }
    return render(request, 'planning/work_orders_schedule.html', context)


@role_required('planner', 'supply_chain', 'supervisor', 'admin')
@require_POST
def work_order_assign_shift_view(request):
    """Assigns an order to a machine/line for a specific shift and date."""
    order_id = request.POST.get('work_order_id')
    shift_id = request.POST.get('shift_id')
    scheduled_date_str = request.POST.get('scheduled_date')
    machine_id = request.POST.get('machine_id') or None
    target_units = request.POST.get('target_units', '1000')
    notes = request.POST.get('notes', '').strip()

    try:
        order = get_object_or_404(WorkOrder, id=order_id)
        shift = get_object_or_404(Shift, id=shift_id)
        machine = Machine.objects.filter(id=machine_id).first() if machine_id else None
        scheduled_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d').date() if scheduled_date_str else timezone.now().date()

        assignment = work_order_service.assign_shift_schedule(
            work_order=order,
            shift=shift,
            scheduled_date=scheduled_date,
            target_units=int(target_units),
            machine=machine,
            notes=notes,
            user=request.user
        )
        messages.success(request, f"Scheduled {order.order_number} to {shift.name} on {scheduled_date}.")
    except Exception as e:
        messages.error(request, f"Failed to schedule shift assignment: {str(e)}")

    redirect_url = f"/work-orders/schedule/?line={request.POST.get('line_id', '')}&date={scheduled_date_str}"
    return redirect(redirect_url)


@role_required('planner', 'supply_chain', 'supervisor', 'admin')
def work_orders_materials_view(request):
    """
    Component Material Delivery & Staging Checklist (/work-orders/materials/).
    Tracks staging readiness of Preforms, Caps, Labels, and Cartons.
    """
    active_orders = WorkOrder.objects.filter(
        status__in=['PLANNED', 'RELEASED', 'IN_PROGRESS']
    ).select_related('product', 'line')

    selected_order_id = request.GET.get('order')
    if selected_order_id:
        materials = WorkOrderMaterial.objects.filter(work_order_id=selected_order_id).select_related('work_order', 'staged_by')
        selected_order = WorkOrder.objects.filter(id=selected_order_id).first()
    else:
        materials = WorkOrderMaterial.objects.filter(
            work_order__in=active_orders
        ).select_related('work_order', 'staged_by')
        selected_order = None

    # Staging Summary
    total_materials = materials.count()
    fully_staged = materials.filter(status='STAGED').count()
    shortages = materials.filter(status='SHORTAGE').count()
    readiness_pct = round((fully_staged / total_materials) * 100, 1) if total_materials > 0 else 100.0

    recent_deliveries = MaterialDelivery.objects.select_related('work_order', 'received_by').all()[:15]

    context = {
        'page_title': 'Material Staging & Delivery Tracker',
        'page_title_ar': 'تتبع تسليم وتجهيز المواد الخام',
        'active_tab': 'materials',
        'active_orders': active_orders,
        'selected_order': selected_order,
        'materials': materials,
        'total_materials': total_materials,
        'fully_staged': fully_staged,
        'shortages': shortages,
        'readiness_pct': readiness_pct,
        'recent_deliveries': recent_deliveries,
    }
    return render(request, 'planning/work_orders_materials.html', context)


@role_required('planner', 'supply_chain', 'supervisor', 'admin')
@require_POST
def work_order_material_stage_action(request, material_id):
    """Stages an increment of raw materials and updates lot traceability."""
    material = get_object_or_404(WorkOrderMaterial, id=material_id)
    staged_qty = request.POST.get('staged_quantity', '0')
    lot_number = request.POST.get('lot_number', '').strip()

    try:
        work_order_service.stage_material(
            material=material,
            staged_qty=Decimal(staged_qty),
            lot_number=lot_number,
            user=request.user
        )
        messages.success(request, f"Staged {staged_qty} {material.unit_of_measure} for {material.name}.")
    except Exception as e:
        messages.error(request, f"Failed to stage material: {str(e)}")

    return redirect(request.META.get('HTTP_REFERER', 'work_orders_materials'))


@role_required('planner', 'supply_chain', 'supervisor', 'admin')
@require_POST
def work_order_material_shortage_action(request, material_id):
    """Flags a raw material shortage condition on an active work order."""
    material = get_object_or_404(WorkOrderMaterial, id=material_id)
    notes = request.POST.get('shortage_notes', '').strip()

    try:
        work_order_service.flag_material_shortage(material, shortage_notes=notes, user=request.user)
        messages.warning(request, f"Shortage flagged on {material.name} ({material.work_order.order_number}).")
    except Exception as e:
        messages.error(request, f"Failed to flag shortage: {str(e)}")

    return redirect(request.META.get('HTTP_REFERER', 'work_orders_materials'))


@role_required('planner', 'supply_chain', 'manager', 'admin')
def work_orders_erp_sync_view(request):
    """
    ERP / Odoo Synchronization Adapter Hub & Conflict Queue (/work-orders/erp-sync/).
    Displays inbound/outbound sync history, connection telemetry, and conflict resolution interface.
    """
    sync_runs = ERPSyncRun.objects.select_related('triggered_by').all()[:20]
    latest_run = sync_runs.first()

    unresolved_conflicts = ERPSyncConflict.objects.filter(
        resolution='UNRESOLVED'
    ).select_related('sync_run', 'work_order', 'work_order__product')

    resolved_conflicts = ERPSyncConflict.objects.exclude(
        resolution='UNRESOLVED'
    ).select_related('sync_run', 'work_order', 'resolved_by')[:10]

    context = {
        'page_title': 'ERP / Odoo Synchronization & Conflict Queue',
        'page_title_ar': 'مزامنة نظام ERP / أودو وطابور النزاعات',
        'active_tab': 'erp_sync',
        'sync_runs': sync_runs,
        'latest_run': latest_run,
        'unresolved_conflicts': unresolved_conflicts,
        'resolved_conflicts': resolved_conflicts,
        'total_conflicts_count': unresolved_conflicts.count(),
    }
    return render(request, 'planning/work_orders_erp_sync.html', context)


@role_required('planner', 'supply_chain', 'admin')
@require_POST
def work_orders_erp_trigger_sync(request):
    """Triggers an immediate inbound sync pull from upstream ERP / Odoo."""
    force_conflict = request.POST.get('force_conflict') == '1'

    try:
        sync_run = erp_service.simulate_erp_pull(user=request.user, force_conflict=force_conflict)
        if sync_run.records_conflicted > 0:
            messages.warning(
                request,
                f"ERP Sync completed with {sync_run.records_conflicted} conflict(s). Review conflict queue below."
            )
        else:
            messages.success(
                request,
                f"ERP Sync successful. Created {sync_run.records_created} new order(s), updated {sync_run.records_updated}."
            )
    except Exception as e:
        messages.error(request, f"ERP Sync failed: {str(e)}")

    return redirect('work_orders_erp_sync')


@role_required('planner', 'supply_chain', 'admin')
@require_POST
def work_orders_erp_resolve_conflict(request, conflict_id):
    """Resolves an ERP Sync conflict item."""
    conflict = get_object_or_404(ERPSyncConflict, id=conflict_id)
    resolution_choice = request.POST.get('resolution')
    notes = request.POST.get('notes', '').strip()

    try:
        erp_service.resolve_erp_conflict(
            conflict=conflict,
            resolution_choice=resolution_choice,
            user=request.user,
            notes=notes
        )
        messages.success(request, f"Conflict for {conflict.external_erp_id} resolved: {conflict.get_resolution_display()}.")
    except Exception as e:
        messages.error(request, f"Failed to resolve conflict: {str(e)}")

    return redirect('work_orders_erp_sync')


@role_required('planner', 'supply_chain', 'admin')
@require_POST
def work_orders_erp_retry(request, run_id):
    """Retries a sync run."""
    sync_run = get_object_or_404(ERPSyncRun, id=run_id)
    try:
        erp_service.retry_sync_run(sync_run, user=request.user)
        messages.success(request, f"Sync run {sync_run.run_id} retry completed. Status: {sync_run.get_status_display()}.")
    except Exception as e:
        messages.error(request, f"Retry failed: {str(e)}")

    return redirect('work_orders_erp_sync')

