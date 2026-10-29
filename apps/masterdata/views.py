"""
Views for Master Data management, including the reference Product Management module.
Strictly implements Section 2.4 of the Master Specification.
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from apps.accounts.decorators import role_required
from apps.accounts.models import AuditEvent
from .models import Product, Process, Factory, Line, Machine


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
