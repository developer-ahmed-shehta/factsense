"""
Views for Master Data management, including the reference Product Management module.
Strictly implements Section 2.4 of the Master Specification.
"""

import uuid
from decimal import Decimal
from datetime import time, datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from apps.accounts.decorators import role_required
from apps.accounts.models import AuditEvent
from .models import (
    Product, Process, Factory, Line, Machine, Shift,
    PlannedBreak, KioskDevice, ReasonCategory, StoppageReason,
    DefectReason, MachineProductRate
)
from .services import INDUSTRY_PRESETS, deploy_line_from_preset, pair_kiosk_device
from .utils import generate_qr_base64


@role_required('planner', 'admin', 'manager', 'supervisor', 'quality', 'supply_chain')
def products_list_view(request):
    """
    Reference Product Management page matching the reference screenshot.
    Full-width table with Product Name, Code, UOM, Design/CAD Link, Ideal Cycle Time,
    Processes (light-blue pills), and Permitted Actions.
    """
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    show_archived = request.GET.get('archived', 'false') == 'true'

    products_qs = Product.objects.prefetch_related('processes').all()

    if not show_archived:
        products_qs = products_qs.filter(is_archived=False)

    if search_query:
        products_qs = products_qs.filter(
            name__icontains=search_query
        ) | products_qs.filter(
            name_ar__icontains=search_query
        ) | products_qs.filter(
            code__icontains=search_query
        )

    if category_filter:
        products_qs = products_qs.filter(category=category_filter)

    categories = Product.objects.values_list('category', flat=True).distinct()
    all_processes = Process.objects.all().order_by('sequence_order')

    # Permissions
    can_edit = request.active_role in ['planner', 'admin']

    context = {
        'products': products_qs,
        'search_query': search_query,
        'category_filter': category_filter,
        'show_archived': show_archived,
        'categories': categories,
        'all_processes': all_processes,
        'can_edit': can_edit,
        'total_products': products_qs.count(),
    }
    return render(request, 'masterdata/products.html', context)


@role_required('planner', 'admin')
@require_POST
def product_add_view(request):
    """
    Creates a new Product (SKU) record with validation and audit trail.
    """
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    category = request.POST.get('category', 'Beverage').strip()
    unit_of_measure = request.POST.get('unit_of_measure', 'Bottle')
    sop_title = request.POST.get('sop_document_title', 'SOP-STD-01.pdf').strip()

    try:
        ideal_cycle_time = Decimal(request.POST.get('ideal_cycle_time_sec', '0.50'))
    except Exception:
        ideal_cycle_time = Decimal('0.50')

    try:
        rated_speed = int(request.POST.get('rated_speed_cpm', '120'))
    except Exception:
        rated_speed = 120

    if not code or not name:
        messages.error(request, 'Product Code and Name are required.')
        return redirect('products_list')

    if Product.objects.filter(code=code).exists():
        messages.error(request, f"Product code '{code}' already exists.")
        return redirect('products_list')

    product = Product.objects.create(
        code=code,
        name=name,
        name_ar=name_ar,
        category=category,
        unit_of_measure=unit_of_measure,
        sop_document_title=sop_title,
        ideal_cycle_time_sec=ideal_cycle_time,
        rated_speed_cpm=rated_speed,
    )

    process_ids = request.POST.getlist('processes')
    if process_ids:
        product.processes.set(process_ids)

    AuditEvent.objects.create(
        actor=request.user,
        active_role=request.active_role,
        action='CREATE_PRODUCT',
        resource='Product',
        resource_id=str(product.id),
        details={'code': code, 'name': name}
    )

    messages.success(request, f"Product '{name}' ({code}) saved successfully.")
    return redirect('products_list')


@role_required('planner', 'admin')
@require_POST
def product_edit_view(request, product_id):
    """
    Updates an existing Product (SKU) record.
    """
    product = get_object_or_404(Product, id=product_id)

    product.name = request.POST.get('name', product.name).strip()
    product.name_ar = request.POST.get('name_ar', product.name_ar).strip()
    product.category = request.POST.get('category', product.category).strip()
    product.unit_of_measure = request.POST.get('unit_of_measure', product.unit_of_measure)
    product.sop_document_title = request.POST.get('sop_document_title', product.sop_document_title).strip()

    try:
        product.ideal_cycle_time_sec = Decimal(request.POST.get('ideal_cycle_time_sec', str(product.ideal_cycle_time_sec)))
    except Exception:
        pass

    try:
        product.rated_speed_cpm = int(request.POST.get('rated_speed_cpm', str(product.rated_speed_cpm)))
    except Exception:
        pass

    product.save()

    process_ids = request.POST.getlist('processes')
    if process_ids:
        product.processes.set(process_ids)

    AuditEvent.objects.create(
        actor=request.user,
        active_role=request.active_role,
        action='UPDATE_PRODUCT',
        resource='Product',
        resource_id=str(product.id),
        details={'code': product.code, 'name': product.name}
    )

    messages.success(request, f"Product '{product.name}' updated successfully.")
    return redirect('products_list')


@role_required('planner', 'admin')
@require_POST
def product_archive_view(request, product_id):
    """
    Archives a product rather than destroying historical data records.
    (Section 2.4 Acceptance Criteria).
    """
    product = get_object_or_404(Product, id=product_id)
    product.is_archived = True
    product.save(update_fields=['is_archived', 'updated_at'])

    AuditEvent.objects.create(
        actor=request.user,
        active_role=request.active_role,
        action='ARCHIVE_PRODUCT',
        resource='Product',
        resource_id=str(product.id),
        details={'code': product.code}
    )

    messages.info(request, f"Product '{product.name}' ({product.code}) archived. Historical records preserved.")
    return redirect('products_list')


# ==============================================================================
# Batch 2 Deliverables: 60-Second Onboarding Wizard & Presets (F11)
# ==============================================================================

@role_required('planner', 'admin')
def wizard_view(request):
    """
    60-Second Onboarding Wizard (Section 7.8, F11):
    Deploy a complete packaging line from scratch using 1-Click Industry Presets:
    - Bottled Water (High Speed, 6 machines, 120 CPM Bottleneck)
    - Carbonated Soft Drinks (CSD, 5 machines, 150 CPM Bottleneck)
    - Edible Oil & Condiments (4 machines, 90 CPM Bottleneck)
    """
    factories = Factory.objects.filter(is_active=True)
    if not factories.exists():
        # Fallback create default factory
        factories = [Factory.objects.create(code='CAIRO-PLANT-01', name='Cairo Bottling Facility')]

    if request.method == 'POST':
        preset_key = request.POST.get('preset_key', 'WATER').strip().upper()
        line_code = request.POST.get('line_code', '').strip().upper()
        line_name = request.POST.get('line_name', '').strip()
        factory_id = request.POST.get('factory_id')
        target_oee = request.POST.get('target_oee', '85.0')

        factory = Factory.objects.filter(id=factory_id).first() or factories[0]

        preset = INDUSTRY_PRESETS.get(preset_key, INDUSTRY_PRESETS['WATER'])
        if not line_code:
            # Generate unique code if not provided
            seq_num = factory.lines.count() + 1
            line_code = f"LINE-{preset_key}-{seq_num:02d}"
        if not line_name:
            line_name = f"{preset['title']} #{factory.lines.count() + 1}"

        try:
            target_oee_val = float(target_oee)
        except ValueError:
            target_oee_val = 85.0

        line, machines, sku = deploy_line_from_preset(
            factory=factory,
            line_code=line_code,
            line_name=line_name,
            preset_key=preset_key,
            target_oee=target_oee_val,
            user=request.user
        )

        messages.success(
            request,
            f"Line '{line.name}' ({line.code}) deployed in 60 seconds with {len(machines)} assets and product '{sku.name}'."
        )
        return redirect(f"{reverse('topology')}?line_id={line.id}")

    context = {
        'presets': INDUSTRY_PRESETS,
        'factories': factories,
        'default_factory': factories[0],
    }
    return render(request, 'masterdata/wizard.html', context)


# ==============================================================================
# Batch 2 Deliverables: Interactive Factory Topology Hub & SVG Node Graph (F11)
# ==============================================================================

@role_required('planner', 'admin', 'supervisor', 'manager', 'quality', 'supply_chain', 'maintenance')
def topology_view(request):
    """
    Interactive Factory Topology Hub (/masterdata/topology/):
    Visual SVG node graph representing physical machine sequence on the line.
    Includes animated conveyor flow dots, designated bottleneck highlighting,
    bilingual RTL directional flip, and slide-out telemetry/hardware inspector.
    """
    lines = Line.objects.prefetch_related('machines').all()
    selected_line_id = request.GET.get('line_id')

    selected_line = None
    if selected_line_id:
        selected_line = lines.filter(id=selected_line_id).first()
    if not selected_line:
        selected_line = lines.first()

    machines = []
    svg_nodes = []
    svg_connectors = []
    svg_width = 1100
    svg_height = 240

    # Detect RTL mode
    lang = getattr(request, 'LANGUAGE_CODE', 'en')
    session_lang = request.session.get('django_language') or request.COOKIES.get('factsense_language')
    is_rtl = (session_lang == 'ar' or lang == 'ar')

    if selected_line:
        machines = list(selected_line.machines.all().order_by('sequence_order'))
        count = len(machines)

        if count > 0:
            left_margin = 100
            right_margin = 100
            usable_width = svg_width - (left_margin + right_margin)
            spacing = usable_width / max(1, count - 1) if count > 1 else usable_width / 2

            for i, m in enumerate(machines):
                if is_rtl:
                    # Right-to-Left physical layout
                    cx = int(svg_width - right_margin - (i * spacing))
                else:
                    # Left-to-Right physical layout
                    cx = int(left_margin + (i * spacing))

                cy = 120
                node_data = {
                    'index': i + 1,
                    'machine': m,
                    'cx': cx,
                    'cy': cy,
                    'is_bottleneck': m.is_bottleneck or (selected_line.bottleneck_machine_id == m.id),
                    'paired_kiosks': m.kiosks.all(),
                }
                svg_nodes.append(node_data)

            # Build conveyor connector lines between adjacent nodes
            for i in range(len(svg_nodes) - 1):
                n1 = svg_nodes[i]
                n2 = svg_nodes[i + 1]
                svg_connectors.append({
                    'x1': n1['cx'],
                    'y1': n1['cy'],
                    'x2': n2['cx'],
                    'y2': n2['cy'],
                    'from_machine': n1['machine'].code,
                    'to_machine': n2['machine'].code,
                })

    context = {
        'lines': lines,
        'selected_line': selected_line,
        'machines': machines,
        'svg_nodes': svg_nodes,
        'svg_connectors': svg_connectors,
        'svg_width': svg_width,
        'svg_height': svg_height,
        'is_rtl': is_rtl,
        'total_machines': len(machines),
        'bottleneck_machine': selected_line.bottleneck_machine if selected_line else None,
    }
    return render(request, 'masterdata/topology.html', context)


# ==============================================================================
# Batch 2 Deliverables: Machine Asset Setup & CRUD (F01)
# ==============================================================================

@role_required('planner', 'admin', 'maintenance', 'supervisor')
def machines_list_view(request):
    """
    Machine Asset Setup table (/administration/machines/ and /masterdata/machines/).
    Full-width table with Sequence, Machine Code, Name, Category, Criticality Rank,
    Bottleneck status, Ideal CPM, Sensor Protocol, and Paired Kiosks.
    """
    line_filter = request.GET.get('line', '').strip()
    lines = Line.objects.all().order_by('factory__code', 'sequence')
    
    machines_qs = Machine.objects.select_related('line', 'line__factory').prefetch_related('kiosks').all()
    if line_filter:
        machines_qs = machines_qs.filter(line__id=line_filter)

    can_edit = request.active_role in ['planner', 'admin']

    context = {
        'machines': machines_qs,
        'lines': lines,
        'line_filter': line_filter,
        'can_edit': can_edit,
        'total_machines': machines_qs.count(),
    }
    return render(request, 'masterdata/machines.html', context)


@role_required('planner', 'admin')
@require_POST
def machine_add_view(request):
    """
    Creates a new machine asset with sequence, criticality, and sensor configuration.
    """
    line_id = request.POST.get('line_id')
    line = get_object_or_404(Line, id=line_id)

    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    category = request.POST.get('category', 'FILLER')
    criticality = request.POST.get('criticality_rank', 'B')
    sensor_proto = request.POST.get('sensor_protocol', 'SIMULATED')
    sensor_ip = request.POST.get('sensor_ip', '').strip() or None
    is_bn = request.POST.get('is_bottleneck') == 'on'

    try:
        seq = int(request.POST.get('sequence_order', '10'))
    except ValueError:
        seq = 10

    try:
        cpm = float(request.POST.get('ideal_run_rate_cpm', '120.0'))
    except ValueError:
        cpm = 120.0

    if not code or not name:
        messages.error(request, 'Machine Code and Name are required.')
        return redirect('machines_list')

    if Machine.objects.filter(line=line, code=code).exists():
        messages.error(request, f"Machine with code '{code}' already exists on line '{line.name}'.")
        return redirect('machines_list')

    mach = Machine.objects.create(
        line=line,
        code=code,
        name=name,
        name_ar=name_ar,
        category=category,
        sequence_order=seq,
        criticality_rank=criticality,
        ideal_run_rate_cpm=cpm,
        is_bottleneck=is_bn,
        sensor_protocol=sensor_proto,
        sensor_ip=sensor_ip,
    )

    if is_bn:
        line.bottleneck_machine = mach
        line.save()

    AuditEvent.objects.create(
        actor=request.user,
        active_role=request.active_role,
        action='CREATE_MACHINE',
        resource='Machine',
        resource_id=str(mach.id),
        details={'code': code, 'line': line.code, 'bottleneck': is_bn}
    )

    messages.success(request, f"Machine '{mach.name}' ({mach.code}) created successfully.")
    return redirect('machines_list')


@role_required('planner', 'admin')
@require_POST
def machine_edit_view(request, machine_id):
    """
    Edits machine parameters and bottleneck assignment.
    """
    mach = get_object_or_404(Machine, id=machine_id)
    mach.name = request.POST.get('name', mach.name).strip()
    mach.name_ar = request.POST.get('name_ar', mach.name_ar).strip()
    mach.category = request.POST.get('category', mach.category)
    mach.criticality_rank = request.POST.get('criticality_rank', mach.criticality_rank)
    mach.sensor_protocol = request.POST.get('sensor_protocol', mach.sensor_protocol)
    mach.sensor_ip = request.POST.get('sensor_ip', '').strip() or None

    try:
        mach.sequence_order = int(request.POST.get('sequence_order', str(mach.sequence_order)))
    except ValueError:
        pass

    try:
        mach.ideal_run_rate_cpm = float(request.POST.get('ideal_run_rate_cpm', str(mach.ideal_run_rate_cpm)))
    except ValueError:
        pass

    is_bn = request.POST.get('is_bottleneck') == 'on'
    mach.is_bottleneck = is_bn
    mach.save()

    if is_bn:
        mach.line.bottleneck_machine = mach
        mach.line.save()

    AuditEvent.objects.create(
        actor=request.user,
        active_role=request.active_role,
        action='UPDATE_MACHINE',
        resource='Machine',
        resource_id=str(mach.id),
        details={'code': mach.code, 'bottleneck': is_bn}
    )

    messages.success(request, f"Machine '{mach.name}' updated successfully.")
    return redirect('machines_list')


# ==============================================================================
# Batch 2 Deliverables: MachineProductRate Speed Matrix (F01)
# ==============================================================================

@role_required('planner', 'admin', 'supervisor', 'manager')
def rates_matrix_view(request):
    """
    Machine-Product Rated Speed Matrix (/planning/rates/ and /masterdata/rates/).
    Displays specific rated speeds (CPM) and ideal cycle times (sec) for each
    Machine x Product pairing.
    """
    lines = Line.objects.all().order_by('factory__code', 'sequence')
    line_filter = request.GET.get('line', '').strip()
    
    machines_qs = Machine.objects.select_related('line').all().order_by('line__sequence', 'sequence_order')
    if line_filter:
        machines_qs = machines_qs.filter(line__id=line_filter)

    products = Product.objects.filter(is_archived=False).order_by('code')
    rates = MachineProductRate.objects.select_related('machine', 'product').all()

    # Build matrix map: (machine_id, product_id) -> rate
    matrix_map = {}
    for r in rates:
        matrix_map[(r.machine_id, r.product_id)] = r

    can_edit = request.active_role in ['planner', 'admin']

    context = {
        'lines': lines,
        'line_filter': line_filter,
        'machines': machines_qs,
        'products': products,
        'matrix_map': matrix_map,
        'can_edit': can_edit,
    }
    return render(request, 'masterdata/rates.html', context)


@role_required('planner', 'admin')
@require_POST
def rate_update_view(request):
    """
    Creates or updates a specific MachineProductRate entry.
    """
    machine_id = request.POST.get('machine_id')
    product_id = request.POST.get('product_id')
    machine = get_object_or_404(Machine, id=machine_id)
    product = get_object_or_404(Product, id=product_id)

    try:
        cpm = float(request.POST.get('rated_speed_cpm', '120.0'))
    except ValueError:
        cpm = 120.0

    try:
        sec = float(request.POST.get('ideal_cycle_time_sec', '0.50'))
        if sec <= 0 and cpm > 0:
            sec = round(60.0 / cpm, 2)
    except ValueError:
        sec = round(60.0 / cpm, 2) if cpm > 0 else 0.50

    rate, created = MachineProductRate.objects.update_or_create(
        machine=machine,
        product=product,
        defaults={
            'rated_speed_cpm': cpm,
            'ideal_cycle_time_sec': sec,
        }
    )

    messages.success(request, f"Rate for {machine.code} x {product.code} set to {cpm} CPM ({sec}s).")
    return redirect('rates_matrix')


# ==============================================================================
# Batch 2 Deliverables: Shifts, Schedules & Planned Breaks (F01)
# ==============================================================================

@role_required('supervisor', 'planner', 'admin', 'manager')
def shifts_list_view(request):
    """
    Shift Lifecycle & Planned Breaks (/shifts/ and /masterdata/shifts/).
    Displays Shift timings, Scheduled Production Window, Excluded Unpaid Breaks,
    and Net Planned Operating Minutes under ISO 22400 OEE basis.
    """
    factories = Factory.objects.all()
    shifts_qs = Shift.objects.prefetch_related('breaks').select_related('factory').all().order_by('sequence', 'start_time')

    can_edit = request.active_role in ['planner', 'admin', 'supervisor']

    context = {
        'shifts': shifts_qs,
        'factories': factories,
        'can_edit': can_edit,
        'total_shifts': shifts_qs.count(),
    }
    return render(request, 'masterdata/shifts.html', context)


@role_required('planner', 'admin', 'supervisor')
@require_POST
def shift_add_view(request):
    """
    Adds a new factory shift.
    """
    factory_id = request.POST.get('factory_id')
    factory = get_object_or_404(Factory, id=factory_id)
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    start_time_str = request.POST.get('start_time', '07:00')
    end_time_str = request.POST.get('end_time', '15:00')

    try:
        st_parts = [int(p) for p in start_time_str.split(':')]
        st = time(st_parts[0], st_parts[1])
        et_parts = [int(p) for p in end_time_str.split(':')]
        et = time(et_parts[0], et_parts[1])
    except Exception:
        messages.error(request, 'Invalid time format. Please use HH:MM.')
        return redirect('shifts_list')

    try:
        seq = int(request.POST.get('sequence', '1'))
        unpaid = int(request.POST.get('unpaid_break_minutes', '30'))
    except ValueError:
        seq = 1
        unpaid = 30

    shift = Shift.objects.create(
        factory=factory,
        code=code,
        name=name,
        name_ar=name_ar,
        start_time=st,
        end_time=et,
        sequence=seq,
        unpaid_break_minutes=unpaid,
    )

    messages.success(request, f"Shift '{shift.name}' ({shift.code}) added successfully.")
    return redirect('shifts_list')


@role_required('planner', 'admin', 'supervisor')
@require_POST
def break_add_view(request):
    """
    Adds a planned non-working break to a specific shift.
    """
    shift_id = request.POST.get('shift_id')
    shift = get_object_or_404(Shift, id=shift_id)

    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    start_time_str = request.POST.get('start_time', '12:00')
    end_time_str = request.POST.get('end_time', '12:30')
    is_unpaid = request.POST.get('is_unpaid') == 'on'

    try:
        st_parts = [int(p) for p in start_time_str.split(':')]
        st = time(st_parts[0], st_parts[1])
        et_parts = [int(p) for p in end_time_str.split(':')]
        et = time(et_parts[0], et_parts[1])
        duration = int(request.POST.get('duration_minutes', '30'))
    except Exception:
        duration = 30
        st = time(12, 0)
        et = time(12, 30)

    PlannedBreak.objects.create(
        shift=shift,
        name=name,
        name_ar=name_ar,
        start_time=st,
        end_time=et,
        duration_minutes=duration,
        is_unpaid=is_unpaid,
    )

    messages.success(request, f"Planned break '{name}' added to {shift.name}.")
    return redirect('shifts_list')


# ==============================================================================
# Batch 2 Deliverables: Stoppage & Defect Taxonomies (F01)
# ==============================================================================

@role_required('planner', 'admin', 'quality', 'supervisor', 'maintenance')
def reasons_taxonomies_view(request):
    """
    Stoppage & Defect Reason Taxonomies (/planning/reasons/ and /masterdata/reasons/).
    Hierarchical downtime reasons tagged with TPM Loss Category and responsible department.
    Defect scrap reasons tagged with default disposition (Scrap, Rework, Quarantine).
    """
    categories = ReasonCategory.objects.prefetch_related('reasons').all().order_by('sequence')
    stoppage_reasons = StoppageReason.objects.select_related('category').all().order_by('category__sequence', 'code')
    defect_reasons = DefectReason.objects.all().order_by('category', 'code')

    can_edit = request.active_role in ['planner', 'admin']

    context = {
        'categories': categories,
        'stoppage_reasons': stoppage_reasons,
        'defect_reasons': defect_reasons,
        'can_edit': can_edit,
    }
    return render(request, 'masterdata/reasons.html', context)


@role_required('planner', 'admin')
@require_POST
def reason_add_view(request):
    """
    Creates a new stoppage reason.
    """
    cat_id = request.POST.get('category_id')
    category = get_object_or_404(ReasonCategory, id=cat_id)
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    tpm_loss = request.POST.get('tpm_loss_type', 'AVAILABILITY_BREAKDOWN')
    is_planned = request.POST.get('is_planned') == 'on'
    force_lg = request.POST.get('force_logout') == 'on'

    try:
        std_res = int(request.POST.get('standard_resolution_min', '15'))
    except ValueError:
        std_res = 15

    StoppageReason.objects.create(
        category=category,
        code=code,
        name=name,
        name_ar=name_ar,
        tpm_loss_type=tpm_loss,
        is_planned=is_planned,
        force_logout=force_lg,
        standard_resolution_min=std_res,
    )

    messages.success(request, f"Stoppage reason '{name}' ({code}) created successfully.")
    return redirect('reasons_taxonomies')


@role_required('planner', 'admin')
@require_POST
def defect_add_view(request):
    """
    Creates a new defect / scrap classification reason.
    """
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    cat = request.POST.get('category', 'Packaging').strip()
    disp = request.POST.get('default_disposition', 'SCRAP')

    DefectReason.objects.create(
        code=code,
        name=name,
        name_ar=name_ar,
        category=cat,
        default_disposition=disp,
    )

    messages.success(request, f"Defect reason '{name}' ({code}) created successfully.")
    return redirect('reasons_taxonomies')


# ==============================================================================
# Batch 2 Deliverables: Process Catalog (F01)
# ==============================================================================

@role_required('planner', 'admin')
def processes_list_view(request):
    """
    Process Catalog & Routing Steps (/planning/processes/ and /masterdata/processes/).
    """
    processes_qs = Process.objects.prefetch_related('products').all().order_by('sequence_order')
    can_edit = request.active_role in ['planner', 'admin']

    context = {
        'processes': processes_qs,
        'can_edit': can_edit,
        'total_processes': processes_qs.count(),
    }
    return render(request, 'masterdata/processes.html', context)


@role_required('planner', 'admin')
@require_POST
def process_add_view(request):
    """
    Creates a new production process routing step.
    """
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    try:
        seq = int(request.POST.get('sequence_order', '1'))
    except ValueError:
        seq = 1

    Process.objects.create(
        code=code,
        name=name,
        name_ar=name_ar,
        sequence_order=seq,
    )
    messages.success(request, f"Process '{name}' ({code}) added successfully.")
    return redirect('processes_list')


# ==============================================================================
# Batch 2 Deliverables: Kiosk Hardware Pairing & Gateway QR Onboarding (F11, F19)
# ==============================================================================

@role_required('admin', 'planner', 'supervisor', 'maintenance')
def kiosk_pairing_view(request):
    """
    Hardware Kiosk & IoT Gateway Enrollment (/administration/gateways/ and /masterdata/kiosk-pairing/).
    Displays QR Code claim codes, enrolled devices, and session exclusivity controls.
    """
    devices = KioskDevice.objects.select_related('machine', 'machine__line').all().order_by('-created_at')
    machines = Machine.objects.all().order_by('line__sequence', 'sequence_order')

    # Generate a fresh sample QR Code for immediate pairing claim
    sample_claim_code = f"CLAIM-{uuid.uuid4().hex[:6].upper()}"
    claim_url = request.build_absolute_uri(f"{reverse('kiosk_pairing')}?claim_code={sample_claim_code}")
    qr_base64 = generate_qr_base64(claim_url)

    selected_claim = request.GET.get('claim_code', '').strip()

    can_edit = request.active_role in ['admin', 'supervisor']

    context = {
        'devices': devices,
        'machines': machines,
        'sample_claim_code': sample_claim_code,
        'qr_base64': qr_base64,
        'selected_claim': selected_claim,
        'can_edit': can_edit,
        'total_devices': devices.count(),
    }
    return render(request, 'masterdata/gateways.html', context)


@role_required('admin', 'supervisor', 'planner')
@require_POST
def claim_kiosk_view(request):
    """
    Pairs or activates a hardware kiosk / edge gateway with a selected machine.
    """
    claim_code = request.POST.get('claim_code', '').strip().upper()
    machine_id = request.POST.get('machine_id')
    device_name = request.POST.get('device_name', '').strip()

    machine = Machine.objects.filter(id=machine_id).first() if machine_id else None
    client_ip = request.META.get('REMOTE_ADDR')

    kiosk = pair_kiosk_device(
        claim_code=claim_code,
        machine=machine,
        ip_address=client_ip,
        user=request.user
    )

    if device_name:
        kiosk.device_name = device_name
        kiosk.save(update_fields=['device_name'])

    messages.success(
        request,
        f"Device '{kiosk.device_name}' successfully paired with {kiosk.machine.name if kiosk.machine else 'system'}."
    )
    return redirect('kiosk_pairing')

