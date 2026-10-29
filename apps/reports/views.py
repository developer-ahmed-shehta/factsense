"""
Views and Export Endpoints for Shift Handover & Production Reports,
Automated Subscriptions, and Historical Data Explorer.
Fulfills F10 and Batch 7 specifications. Zero-emoji compliant.
"""

import csv
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from apps.accounts.decorators import role_required
from apps.masterdata.models import Line, Shift, Machine
from apps.telemetry.models import DowntimeEvent, TelemetryReading
from apps.operations.models import DefectLog, ShiftHandover
from apps.planning.models import WorkOrder
from apps.reports.models import ReportSubscription, ReportDispatchLog
from apps.reports.services.pdf_generator import generate_shift_handover_pdf
from apps.reports.services.excel_generator import generate_shift_handover_excel
from apps.reports.services.dispatch_service import dispatch_subscription


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def reports_home_view(request):
    """
    Main Production Reports Hub landing (/reports/).
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    selected_line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    shifts = Shift.objects.all().order_by('sequence')
    selected_shift_id = request.GET.get('shift')
    selected_shift = Shift.objects.filter(id=selected_shift_id).first() if selected_shift_id else shifts.first()

    subscriptions = ReportSubscription.objects.filter(line=selected_line).select_related('line') if selected_line else ReportSubscription.objects.none()
    recent_logs = ReportDispatchLog.objects.select_related('subscription').all()[:15]

    context = {
        'page_title': 'Production Reports & Shift Handover',
        'page_title_ar': 'تقارير الإنتاج وتسليم الورديات',
        'active_tab': 'overview',
        'lines': lines,
        'selected_line': selected_line,
        'shifts': shifts,
        'selected_shift': selected_shift,
        'subscriptions': subscriptions,
        'recent_logs': recent_logs,
    }
    return render(request, 'reports/reports_home.html', context)


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
@require_GET
def export_pdf_view(request):
    """
    Generates and downloads official printable PDF Shift Handover report.
    Route: GET /reports/export/pdf/?line_id=&shift_id=
    """
    line_id = request.GET.get('line_id') or request.GET.get('line')
    line = Line.objects.filter(id=line_id).first() if line_id else Line.objects.first()

    shift_id = request.GET.get('shift_id') or request.GET.get('shift')
    shift = Shift.objects.filter(id=shift_id).first() if shift_id else Shift.objects.first()

    if not line:
        return HttpResponse("No line available for export", status=400)

    pdf_buffer = generate_shift_handover_pdf(line=line, shift=shift, user=request.user)
    
    # Audit log
    ReportDispatchLog.objects.create(
        report_type='SHIFT_HANDOVER',
        format='PDF',
        recipient=request.user.email or request.user.username,
        channel='MANUAL_DOWNLOAD',
        status='SENT'
    )

    filename = f"Shift_Handover_{line.code}_{timezone.now().strftime('%Y%m%d')}.pdf"
    response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
@require_GET
def export_excel_view(request):
    """
    Generates and downloads multi-tab structured Excel workbook (.xlsx).
    Route: GET /reports/export/excel/?line_id=&shift_id=
    """
    line_id = request.GET.get('line_id') or request.GET.get('line')
    line = Line.objects.filter(id=line_id).first() if line_id else Line.objects.first()

    shift_id = request.GET.get('shift_id') or request.GET.get('shift')
    shift = Shift.objects.filter(id=shift_id).first() if shift_id else Shift.objects.first()

    if not line:
        return HttpResponse("No line available for export", status=400)

    excel_buffer = generate_shift_handover_excel(line=line, shift=shift, user=request.user)

    # Audit log
    ReportDispatchLog.objects.create(
        report_type='SHIFT_HANDOVER',
        format='EXCEL',
        recipient=request.user.email or request.user.username,
        channel='MANUAL_DOWNLOAD',
        status='SENT'
    )

    filename = f"Shift_Handover_{line.code}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        excel_buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@role_required('supervisor', 'planner', 'manager', 'admin')
def subscriptions_view(request):
    """
    Automated Report Subscriptions Hub (/reports/subscriptions/).
    """
    lines = Line.objects.all()
    subscriptions = ReportSubscription.objects.select_related('line', 'created_by').all()
    recent_logs = ReportDispatchLog.objects.select_related('subscription').all()[:20]

    context = {
        'page_title': 'Automated Report Subscriptions',
        'page_title_ar': 'الاشتراكات الآلية في التقارير (Email / Telegram)',
        'active_tab': 'subscriptions',
        'subscriptions': subscriptions,
        'lines': lines,
        'recent_logs': recent_logs,
    }
    return render(request, 'reports/subscriptions.html', context)


@role_required('supervisor', 'planner', 'manager', 'admin')
@require_POST
def subscription_create_view(request):
    """Creates a new automated report subscription."""
    name = request.POST.get('name', '').strip()
    report_type = request.POST.get('report_type', 'SHIFT_HANDOVER')
    fmt = request.POST.get('format', 'PDF')
    frequency = request.POST.get('frequency', 'END_OF_SHIFT')
    line_id = request.POST.get('line_id')
    recipient_emails = request.POST.get('recipient_emails', '').strip()
    telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()

    line = get_object_or_404(Line, id=line_id)

    sub = ReportSubscription.objects.create(
        name=name or f"{line.name} {report_type}",
        report_type=report_type,
        format=fmt,
        frequency=frequency,
        line=line,
        recipient_emails=recipient_emails,
        telegram_chat_id=telegram_chat_id,
        created_by=request.user,
        is_active=True
    )
    messages.success(request, f"Subscription '{sub.name}' created successfully.")
    return redirect('reports_subscriptions')


@role_required('supervisor', 'planner', 'manager', 'admin')
@require_POST
def subscription_dispatch_now_view(request, sub_id):
    """Triggers an immediate dispatch of a report subscription."""
    sub = get_object_or_404(ReportSubscription, id=sub_id)
    logs = dispatch_subscription(sub, user=request.user)
    messages.success(request, f"Report dispatched to {len(logs)} recipient channel(s).")
    return redirect('reports_subscriptions')


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def historical_explorer_view(request):
    """
    Historical Data & Analytics Center (/reports/explorer/).
    Filterable data explorer across Production, Downtime, Scrap, and Work Orders.
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    selected_line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    dataset_type = request.GET.get('dataset', 'DOWNTIME')

    # Query dataset
    records = []
    if dataset_type == 'DOWNTIME':
        records = DowntimeEvent.objects.filter(
            machine__line=selected_line
        ).select_related('machine', 'reason').order_by('-start_time')[:100]
    elif dataset_type == 'DEFECTS':
        records = DefectLog.objects.filter(
            machine__line=selected_line
        ).select_related('machine', 'reason').order_by('-logged_at')[:100]
    elif dataset_type == 'WORK_ORDERS':
        records = WorkOrder.objects.filter(
            line=selected_line
        ).select_related('product', 'line').order_by('-planned_start')[:100]

    context = {
        'page_title': 'Historical Data & Analytics Explorer',
        'page_title_ar': 'مركز استكشاف البيانات التاريخية والتحليلات',
        'active_tab': 'explorer',
        'lines': lines,
        'selected_line': selected_line,
        'dataset_type': dataset_type,
        'records': records,
        'total_records_count': len(records),
    }
    return render(request, 'reports/historical_explorer.html', context)


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
@require_GET
def historical_export_csv_view(request):
    """
    Exports filtered historical records to CSV format.
    """
    line_id = request.GET.get('line')
    line = Line.objects.filter(id=line_id).first() if line_id else Line.objects.first()
    dataset_type = request.GET.get('dataset', 'DOWNTIME')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="historical_{dataset_type.lower()}_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)

    if dataset_type == 'DOWNTIME':
        writer.writerow(['Machine Code', 'Machine Name', 'TPM Category', 'Reason', 'Start Time', 'End Time', 'Duration (Min)', 'Operator Notes'])
        events = DowntimeEvent.objects.filter(machine__line=line).select_related('machine', 'reason')[:500]
        for ev in events:
            writer.writerow([
                ev.machine.code,
                ev.machine.name,
                ev.tpm_loss_type,
                ev.reason.name if ev.reason else "Unclassified",
                ev.start_time.isoformat(),
                ev.end_time.isoformat() if ev.end_time else "",
                round(ev.duration_seconds / 60.0, 1),
                ev.notes
            ])
    elif dataset_type == 'DEFECTS':
        writer.writerow(['Logged At', 'Machine Code', 'Defect Code', 'Defect Reason', 'Quantity (Pcs)', 'Disposition', 'Scrap Cost'])
        defects = DefectLog.objects.filter(machine__line=line).select_related('machine', 'reason')[:500]
        for d in defects:
            writer.writerow([
                d.logged_at.isoformat(),
                d.machine.code,
                d.reason.code if d.reason else "SCRAP",
                d.reason.name if d.reason else "Production Scrap",
                d.quantity_pieces,
                d.disposition,
                float(d.financial_cost)
            ])
    elif dataset_type == 'WORK_ORDERS':
        writer.writerow(['Order Number', 'ERP ID', 'Product Code', 'Target Quantity', 'Produced Quantity', 'Scrap Quantity', 'Lot Number', 'Status'])
        wos = WorkOrder.objects.filter(line=line)[:500]
        for w in wos:
            writer.writerow([
                w.order_number,
                w.external_erp_id,
                w.product.code,
                w.target_quantity,
                w.produced_quantity,
                w.scrap_quantity,
                w.lot_number,
                w.status
            ])

    return response
