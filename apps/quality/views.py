"""
Quality Assurance, Statistical Process Control (SPC) & Giveaway Analysis Views.
Strictly implements:
- F07: ISO 22400-2 SPC X-bar and R Charts, Gaussian Normal Distribution Curve, Cp and Cpk Indices
- Product Giveaway Financial Cost Calculator & Interactive Recalibration Slider
- Quality Subgroups and Weight Samples Explorer
- Raw CSV Data Export
"""

import csv
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from apps.accounts.decorators import role_required
from apps.masterdata.models import Line, Machine, Product
from apps.operations.models import DefectLog
from apps.quality.models import SPCConfig, QualitySubgroup, QualitySample
from apps.quality.services.spc_service import (
    calculate_spc_metrics, simulate_recalibration, get_or_create_default_spc_config
)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_hub_view(request):
    """
    Quality Assurance & SPC Control Hub (/quality/).
    Displays live X-bar and R charts, Bell Curve, Cp/Cpk capability, and giveaway summary.
    """
    lines = Line.objects.all()
    products = Product.objects.all()
    
    selected_line_id = request.GET.get('line')
    selected_product_id = request.GET.get('product')
    selected_machine_id = request.GET.get('machine')

    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()
    product = Product.objects.filter(id=selected_product_id).first() if selected_product_id else products.first()
    
    machines = line.machines.all() if line else Machine.objects.all()
    machine = Machine.objects.filter(id=selected_machine_id).first() if selected_machine_id else (
        # Default to filler or first machine
        machines.filter(code__icontains='FIL').first() or machines.first()
    )

    spc_data = calculate_spc_metrics(machine=machine, line=line, product=product)

    context = {
        'page_title': 'Quality Assurance & SPC Control Hub',
        'page_title_ar': 'إدارة الجودة والتحكم الإحصائي في العمليات (SPC)',
        'lines': lines,
        'selected_line': line,
        'products': products,
        'selected_product': product,
        'machines': machines,
        'selected_machine': machine,
        'spc': spc_data,
    }
    return render(request, 'portal/quality_home.html', context)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_samples_view(request):
    """
    Weight Samples and Subgroups Ledger (/quality/samples/).
    """
    lines = Line.objects.all()
    products = Product.objects.all()
    
    selected_line_id = request.GET.get('line')
    selected_product_id = request.GET.get('product')

    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()
    product = Product.objects.filter(id=selected_product_id).first() if selected_product_id else products.first()

    samples_qs = QualitySample.objects.all().select_related('machine', 'product', 'operator')
    if line:
        samples_qs = samples_qs.filter(line=line)
    if product:
        samples_qs = samples_qs.filter(product=product)

    recent_samples = samples_qs.order_by('-timestamp')[:100]

    # Also fetch recent subgroups
    subgroups_qs = QualitySubgroup.objects.all().select_related('machine', 'product')
    if line:
        subgroups_qs = subgroups_qs.filter(line=line)
    if product:
        subgroups_qs = subgroups_qs.filter(product=product)
    recent_subgroups = subgroups_qs.order_by('-timestamp')[:30]

    context = {
        'page_title': 'Quality Weight Samples & Subgroups',
        'page_title_ar': 'سجل عينات الوزن والمجموعات الإحصائية',
        'lines': lines,
        'selected_line': line,
        'products': products,
        'selected_product': product,
        'recent_samples': recent_samples,
        'recent_subgroups': recent_subgroups,
    }
    return render(request, 'portal/quality_samples.html', context)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_defects_view(request):
    """
    Quality Defects & Scrap Ledger (/quality/defects/).
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    defects_qs = DefectLog.objects.all().select_related('machine', 'product', 'reason', 'logged_by')
    if line:
        defects_qs = defects_qs.filter(line=line)

    recent_defects = defects_qs.order_by('-timestamp')[:100]
    total_scrap_pieces = sum(d.quantity_pieces for d in recent_defects)
    total_scrap_cost = sum(d.financial_cost for d in recent_defects)

    context = {
        'page_title': 'Defects & Scrap Quality Ledger',
        'page_title_ar': 'سجل العيوب والهدر النوعي',
        'lines': lines,
        'selected_line': line,
        'recent_defects': recent_defects,
        'total_scrap_pieces': total_scrap_pieces,
        'total_scrap_cost': total_scrap_cost,
    }
    return render(request, 'portal/quality_defects.html', context)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_giveaway_view(request):
    """
    Overfill Product Giveaway Analysis & Recalibration Simulator (/quality/giveaway/).
    """
    lines = Line.objects.all()
    products = Product.objects.all()
    
    selected_line_id = request.GET.get('line')
    selected_product_id = request.GET.get('product')

    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()
    product = Product.objects.filter(id=selected_product_id).first() if selected_product_id else products.first()
    
    machines = line.machines.all() if line else Machine.objects.all()
    filler = machines.filter(code__icontains='FIL').first() or machines.first()

    spc_data = calculate_spc_metrics(machine=filler, line=line, product=product)

    context = {
        'page_title': 'Overfill Product Giveaway & Recalibration',
        'page_title_ar': 'تحليل الهدر بالوزن الزائد ومحاكاة إعادة المعايرة',
        'lines': lines,
        'selected_line': line,
        'products': products,
        'selected_product': product,
        'machine': filler,
        'spc': spc_data,
    }
    return render(request, 'portal/quality_giveaway.html', context)


@require_POST
@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_recalibrate_api(request):
    """
    JSON API for interactive recalibration slider.
    POST: { 'offset_grams': -0.80, 'product_id': '...', 'machine_id': '...' }
    """
    offset_grams = request.POST.get('offset_grams', '0.0')
    product_id = request.POST.get('product_id')
    machine_id = request.POST.get('machine_id')

    product = Product.objects.filter(id=product_id).first()
    machine = Machine.objects.filter(id=machine_id).first()

    res = simulate_recalibration(
        target_offset_grams=float(offset_grams),
        machine=machine,
        product=product,
    )
    return JsonResponse(res)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_export_csv(request):
    """
    Exports raw quality weight sample measurements to standard CSV file.
    """
    product_id = request.GET.get('product')
    line_id = request.GET.get('line')

    qs = QualitySample.objects.all().select_related('machine', 'product', 'operator').order_by('-timestamp')
    if product_id:
        qs = qs.filter(product_id=product_id)
    if line_id:
        qs = qs.filter(line_id=line_id)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="factsense_quality_samples_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Sample ID', 'Timestamp (UTC)', 'Machine Code', 'Machine Name',
        'Product SKU', 'Product Name', 'Measured Weight (g)',
        'Nominal Target (g)', 'Deviation (g)', 'Within Spec', 'Operator'
    ])

    for s in qs[:2000]:
        writer.writerow([
            str(s.id),
            s.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            s.machine.code,
            s.machine.name,
            s.product.sku,
            s.product.name,
            f"{s.measured_weight_grams:.2f}",
            f"{s.nominal_target_grams:.2f}",
            f"{s.deviation_grams:+.2f}",
            'YES' if s.is_within_spec else 'NO',
            s.operator.username if s.operator else 'N/A',
        ])

    return response
