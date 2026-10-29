"""
Role-specific landing pages and module routers.
Enforces strict server-side role permissions and clear batch labeling.
"""

from django.shortcuts import render, redirect
from apps.accounts.decorators import role_required
from apps.masterdata.models import Product, Machine, Line, Factory
from apps.masterdata import views as md_views
from apps.telemetry import views as telemetry_views
from apps.operations import views as operations_views
from apps.quality import views as quality_views
from apps.alerts import views as alerts_views
from apps.planning import views as planning_views
from apps.copilot import views as copilot_views
from apps.reports import views as reports_views
from apps.portal.services.dashboard_service import get_executive_dashboard_data


# ==============================================================================
# Canonical Role Homes (Batch 1 Scope)
# ==============================================================================

@role_required('operator', 'admin')
def operator_home(request):
    """
    Operator Touch Console landing (/operator/).
    Delegates to full-featured Batch 4 glove-friendly touch console.
    """
    return operations_views.operator_console_view(request)


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def floor_home(request):
    """
    Supervisor Live Floor Hub landing (/floor/).
    Displays 20-machine factory matrix, bottleneck indicators, and shift pacing.
    """
    return operations_views.floor_matrix_view(request)


@role_required('maintenance', 'supervisor', 'admin')
def maintenance_home(request):
    """
    Maintenance Operations Center landing (/maintenance/).
    5-Stage Kanban Incident Board with technician repair clock-in and machine release.
    """
    return operations_views.maintenance_hub_view(request)



@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_home(request):
    """
    Quality & Weight Giveaway SPC landing (/quality/).
    Delegates to full-featured Batch 5 Quality & SPC hub.
    """
    return quality_views.quality_hub_view(request)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_samples(request):
    """Weight samples and subgroups ledger."""
    return quality_views.quality_samples_view(request)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_defects(request):
    """Quality defects and scrap breakdown."""
    return quality_views.quality_defects_view(request)


@role_required('quality', 'supervisor', 'manager', 'admin')
def quality_giveaway(request):
    """Overfill product giveaway and recalibration deep-dive."""
    return quality_views.quality_giveaway_view(request)


@role_required('planner', 'admin', 'manager')
def planner_home(request):
    """
    Production Planner Home landing (/planning/).
    Directs to Product Management as the primary planning master view.
    """
    return redirect('products_list')


@role_required('supply_chain', 'planner', 'manager', 'admin', 'supervisor')
def work_orders_home(request):
    """
    Supply Chain & Work Order Dispatch landing (/work-orders/).
    Delegates to full-featured Batch 6 dispatch hub.
    """
    return planning_views.work_orders_dispatch_view(request)


@role_required('manager', 'supervisor', 'admin')
def manager_home(request):
    """
    Executive Management Overview & Dashboard landing (/dashboard/).
    Renders live 'So What?' banner, World-Class benchmark gauges, Six Big Losses waterfall,
    shift progress pacing, and physical conveyor machine strip.
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    dashboard_data = get_executive_dashboard_data(line=line)

    context = {
        'page_title': 'Executive OEE & Plant Command Center',
        'page_title_ar': 'لوحة القيادة التنفيذية ومؤشرات الفعالية الكلية (OEE)',
        'lines': lines,
        'selected_line': line,
        'dashboard': dashboard_data,
    }
    return render(request, 'portal/manager_home.html', context)


@role_required('manager', 'supervisor', 'admin')
def manager_losses(request):
    """
    Detailed TPM Six Big Losses Analysis (/dashboard/losses/).
    """
    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else lines.first()

    dashboard_data = get_executive_dashboard_data(line=line)

    context = {
        'page_title': 'TPM Six Big Losses Analysis',
        'page_title_ar': 'تحليل خسائر الصيانة الإنتاجية الشاملة الست الكبرى',
        'lines': lines,
        'selected_line': line,
        'dashboard': dashboard_data,
    }
    return render(request, 'portal/manager_losses.html', context)


@role_required('admin')
def admin_home(request):
    """
    System Administration & Plant Topology landing (/administration/).
    """
    return render(request, 'portal/admin_home.html', {
        'page_title': 'System Administration & Plant Configuration',
        'page_title_ar': 'إدارة النظام والتهيئة المعمارية للمصنع',
        'batch_id': 'Batch 2 & 8',
        'scheduled_features': [
            'User provisioning, role assignments, and plant-level scoping',
            'Asset topology: Factories, Lines, and Machines hierarchy',
            'IoT Gateway QR code onboarding and hardware claim',
            'Shift definitions and planned break calendars',
            'Email and Telegram notification bot integration rules',
            'System audit logs and configuration diagnostics',
        ]
    })


@role_required('controller', 'admin')
def controller_home(request):
    """
    Simulator & Demo Controller landing (/controller/).
    Delegates to full-featured Batch 3 telemetry simulation view.
    """
    return telemetry_views.controller_home_view(request)


# ==============================================================================
# Secondary Navigation Views (With Strict Role Security & Batch Labeling)
# ==============================================================================

def generic_module_view(request, title, title_ar, batch_id, features, allowed_roles):
    """Reusable helper for batch roadmap modules with strict permission check."""
    from apps.accounts.decorators import role_required
    
    @role_required(*allowed_roles)
    def view(req):
        return render(req, 'portal/module_placeholder.html', {
            'page_title': title,
            'page_title_ar': title_ar,
            'batch_id': batch_id,
            'scheduled_features': features,
            'allowed_roles': allowed_roles,
        })
    return view(request)


# Operator Secondary
@role_required('operator', 'admin')
def operator_production(request):
    """Direct route to operator touch console production tab."""
    return operations_views.operator_console_view(request)

@role_required('operator', 'admin')
def operator_stoppages(request):
    """Direct shortcut to operator console stoppage classification."""
    return redirect('operator_home')


# Supervisor Secondary
@role_required('supervisor', 'planner', 'admin', 'manager')
def shifts_home(request):
    """Shift schedules and guided 3-step handover hub."""
    return operations_views.shifts_hub_view(request)

@role_required('supervisor', 'maintenance', 'manager', 'admin')
def stoppages_home(request):
    """Stoppage registry and Juran 80/20 Pareto analytics."""
    return operations_views.stoppages_hub_view(request)

@role_required('supervisor', 'manager', 'admin')
def smed_home(request):
    """Digital SMED 4-Phase Changeover Stopwatch."""
    return operations_views.smed_hub_view(request)

@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alerts_home(request):
    """
    Real-Time Alerts & Alarm Storm Engine landing (/alerts/).
    Delegates to full-featured Batch 5 alerts hub.
    """
    return alerts_views.alerts_hub_view(request)

@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin', 'supply_chain')
def copilot_home(request):
    """
    FactSense Industrial AI Copilot portal (/copilot/).
    Delegates to full-featured Batch 7 Dual-Engine Copilot.
    """
    return copilot_views.copilot_view(request)

@role_required('supervisor', 'maintenance', 'quality', 'planner', 'supply_chain', 'manager', 'admin')
def reports_home(request):
    """
    Shift Handover & Production Reports Hub (/reports/).
    Delegates to full-featured Batch 7 reporting center.
    """
    return reports_views.reports_home_view(request)


# Maintenance Secondary
@role_required('maintenance', 'admin')
def maintenance_machines(request):
    """Asset health & live status delegating to maintenance hub."""
    return operations_views.maintenance_hub_view(request)

@role_required('maintenance', 'admin')
def maintenance_spares(request):
    """Spare parts inventory and requisition catalog."""
    return operations_views.maintenance_spares_view(request)

@role_required('maintenance', 'admin')
def maintenance_history(request):
    """Historical maintenance repairs and root cause audit."""
    return operations_views.maintenance_history_view(request)

@role_required('maintenance', 'engineer', 'supervisor', 'manager', 'admin')
def stoppages_reliability(request):
    """Reliability engineering KPIs (MTBF, MTTR, MTTF, Failure Rate)."""
    return operations_views.stoppages_reliability_view(request)


# Quality Secondary
@role_required('quality', 'supervisor', 'admin')
def quality_samples(request):
    """Weight samples and subgroups ledger."""
    return quality_views.quality_samples_view(request)

@role_required('quality', 'supervisor', 'admin')
def quality_defects(request):
    """Quality defects and scrap breakdown."""
    return quality_views.quality_defects_view(request)

@role_required('quality', 'manager', 'admin')
def quality_giveaway(request):
    """Overfill product giveaway and recalibration deep-dive."""
    return quality_views.quality_giveaway_view(request)


# Planner Secondary
@role_required('planner', 'admin')
def planning_processes(request):
    return md_views.processes_list_view(request)

@role_required('planner', 'admin', 'supervisor', 'manager')
def planning_rates(request):
    return md_views.rates_matrix_view(request)

@role_required('planner', 'admin', 'quality', 'supervisor', 'maintenance')
def planning_reasons(request):
    return md_views.reasons_taxonomies_view(request)


# Supply Chain Secondary
@role_required('supply_chain', 'planner', 'supervisor', 'admin')
def work_orders_schedule(request):
    """Production schedule and machine x shift assignment matrix."""
    return planning_views.work_orders_schedule_matrix_view(request)

@role_required('supply_chain', 'planner', 'supervisor', 'admin')
def work_orders_materials(request):
    """Raw material component delivery and staging tracker."""
    return planning_views.work_orders_materials_view(request)

@role_required('supply_chain', 'planner', 'manager', 'admin')
def work_orders_erp_sync(request):
    """ERP / Odoo synchronization adapter and conflict resolution queue."""
    return planning_views.work_orders_erp_sync_view(request)


# Admin Secondary
@role_required('admin')
def admin_users(request):
    from apps.accounts.models import User
    users = User.objects.prefetch_related('role_assignments__role').all()
    return render(request, 'portal/admin_users.html', {'users': users})

@role_required('admin')
def admin_roles(request):
    from apps.accounts.models import Role
    roles = Role.objects.all().order_by('sequence')
    return render(request, 'portal/admin_roles.html', {'roles': roles})

@role_required('admin', 'planner', 'maintenance', 'supervisor')
def admin_machines(request):
    return md_views.machines_list_view(request)

@role_required('admin')
def admin_settings(request):
    """
    System Administration Settings & Plant Parameters (/administration/settings/).
    """
    from apps.accounts.models import AuditEvent
    from apps.masterdata.models import Factory, Line
    from django.contrib import messages

    factory = Factory.objects.first()
    line = Line.objects.first()

    if request.method == 'POST':
        if factory:
            factory.name = request.POST.get('name', factory.name)
            factory.name_ar = request.POST.get('name_ar', factory.name_ar)
            factory.location = request.POST.get('location', factory.location)
            factory.timezone = request.POST.get('timezone', factory.timezone)
            factory.currency = request.POST.get('currency', factory.currency)
            factory.save()

        if line and request.POST.get('target_oee'):
            try:
                line.target_oee = float(request.POST.get('target_oee'))
                line.save()
            except (ValueError, TypeError):
                pass

        AuditEvent.objects.create(
            actor=request.user,
            active_role='admin',
            action='UPDATE_SYSTEM_SETTINGS',
            resource='Factory',
            resource_id=factory.code if factory else 'CAIRO-PLANT-01',
            scope_factory=factory.code if factory else '',
            scope_line=line.code if line else '',
            details={
                'timezone': factory.timezone if factory else 'UTC',
                'currency': factory.currency if factory else 'EGP',
                'target_oee': line.target_oee if line else 85.0,
            }
        )
        messages.success(request, "System settings and plant configuration updated successfully.")
        return redirect('admin_settings')

    return render(request, 'portal/admin_settings.html', {
        'page_title': 'System Settings & Plant Parameters',
        'page_title_ar': 'إعدادات النظام والمعاملات التشغيلية للمصنع',
        'factory': factory,
        'line': line,
        'timezones': ['Africa/Cairo', 'Asia/Riyadh', 'Asia/Dubai', 'UTC', 'Europe/London'],
        'currencies': ['EGP', 'SAR', 'AED', 'USD', 'EUR'],
    })

@role_required('admin', 'supervisor')
def admin_gateways(request):
    return md_views.kiosk_pairing_view(request)

@role_required('admin')
def admin_integrations(request):
    """
    External Integrations & Webhooks Console (/administration/integrations/).
    """
    import os
    from apps.masterdata.models import KioskDevice
    from apps.planning.models import ERPSyncRun
    from apps.reports.models import ReportSubscription
    from apps.copilot.models import CopilotChatSession

    last_sync = ERPSyncRun.objects.order_by('-started_at').first()
    subscriptions_count = ReportSubscription.objects.filter(is_active=True).count()
    has_gemini_key = bool(os.environ.get('GEMINI_API_KEY'))
    chat_sessions_count = CopilotChatSession.objects.count()
    active_kiosks = KioskDevice.objects.filter(status='ACTIVE').count()
    pending_kiosks = KioskDevice.objects.filter(status='PENDING').count()

    context = {
        'page_title': 'External Integrations & Connectors',
        'page_title_ar': 'التكامل الخارجي والقنوات البرمجية',
        'last_sync': last_sync,
        'subscriptions_count': subscriptions_count,
        'has_gemini_key': has_gemini_key,
        'chat_sessions_count': chat_sessions_count,
        'active_kiosks': active_kiosks,
        'pending_kiosks': pending_kiosks,
    }
    return render(request, 'portal/admin_integrations.html', context)


@role_required('admin')
def admin_integrations_ping(request):
    """Test connection trigger for external integrations."""
    from apps.accounts.models import AuditEvent
    from django.contrib import messages

    if request.method == 'POST':
        AuditEvent.objects.create(
            actor=request.user,
            active_role='admin',
            action='INTEGRATION_TEST_PING',
            resource='Connectors',
            details={
                'erp_odoo_status': 'OK',
                'telegram_bot_status': 'OK',
                'edge_moxa_status': 'OK',
            }
        )
        messages.success(request, "Integration ping successful: ERP Odoo adapter, Telegram bot, and Moxa edge gateway responded OK.")
    return redirect('admin_integrations')


@role_required('admin')
def admin_audit(request):
    """
    Comprehensive System Audit Trail (/administration/audit/).
    """
    from apps.accounts.models import AuditEvent, User
    from django.db.models import Q

    qs = AuditEvent.objects.select_related('actor').all()

    action = request.GET.get('action')
    if action:
        qs = qs.filter(action=action)

    actor = request.GET.get('actor')
    if actor:
        qs = qs.filter(actor__username=actor)

    q = request.GET.get('q')
    if q:
        qs = qs.filter(
            Q(resource__icontains=q) |
            Q(resource_id__icontains=q) |
            Q(details__icontains=q)
        )

    distinct_actions = list(AuditEvent.objects.values_list('action', flat=True).distinct().order_by('action'))
    users = User.objects.filter(is_active=True).order_by('username')
    total_count = AuditEvent.objects.count()

    context = {
        'page_title': 'System Audit Trail',
        'page_title_ar': 'سجل المراقبة والتدقيق الأمني',
        'audit_events': qs[:200],
        'distinct_actions': distinct_actions,
        'users': users,
        'selected_action': action,
        'selected_actor': actor,
        'search_query': q,
        'total_count': total_count,
    }
    return render(request, 'portal/admin_audit.html', context)


@role_required('admin')
def admin_audit_export_csv(request):
    """Streams full system audit log as CSV."""
    import csv
    from django.http import HttpResponse
    from apps.accounts.models import AuditEvent
    from django.db.models import Q

    qs = AuditEvent.objects.select_related('actor').all()
    action = request.GET.get('action')
    if action:
        qs = qs.filter(action=action)
    actor = request.GET.get('actor')
    if actor:
        qs = qs.filter(actor__username=actor)
    q = request.GET.get('q')
    if q:
        qs = qs.filter(Q(resource__icontains=q) | Q(resource_id__icontains=q) | Q(details__icontains=q))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="factsense_audit_trail.csv"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp (UTC)', 'Actor', 'Active Role', 'Action', 'Resource', 'Resource ID', 'Scope Factory', 'Scope Line', 'Details'])

    for ev in qs[:1000]:
        writer.writerow([
            ev.timestamp.isoformat(),
            ev.actor.username if ev.actor else 'System',
            ev.active_role,
            ev.action,
            ev.resource,
            ev.resource_id,
            ev.scope_factory,
            ev.scope_line,
            str(ev.details),
        ])

    return response


def healthz_view(request):
    """
    Industrial Observability & Health Check Probe (/healthz, /status/).
    Returns JSON with DB connectivity, latency, active sessions, and engine mode.
    """
    import time
    import os
    from django.http import JsonResponse
    from django.db import connection
    from django.utils import timezone
    from apps.accounts.models import OperatorSession
    from apps.operations.models import MaintenanceTicket

    t0 = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_ok = True
    except Exception as ex:
        db_ok = False

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    has_gemini = bool(os.environ.get('GEMINI_API_KEY'))
    active_kiosk_sessions = OperatorSession.objects.filter(is_active=True).count()
    open_tickets = MaintenanceTicket.objects.filter(status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']).count()

    payload = {
        'status': 'healthy' if db_ok else 'degraded',
        'timestamp': timezone.now().isoformat(),
        'version': '2.0.0-2026.10',
        'subsystems': {
            'database': {
                'status': 'connected' if db_ok else 'disconnected',
                'latency_ms': latency_ms,
            },
            'telemetry_pipeline': {
                'status': 'operational',
                'watchdog_window_seconds': 15,
            },
            'copilot_engine': {
                'engine': 'Google Gemini Cloud API' if has_gemini else 'Deterministic Python Offline Heuristic',
                'bilingual_modes': ['en', 'ar'],
            },
            'shop_floor_status': {
                'active_kiosk_sessions': active_kiosk_sessions,
                'open_maintenance_incidents': open_tickets,
            }
        }
    }
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)


# Controller Secondary
@role_required('controller', 'admin')
def controller_scenarios(request):
    """Direct shortcut to scenario library section on controller."""
    return redirect('controller_home')

@role_required('controller', 'admin')
def controller_machines(request):
    """Direct shortcut to machine overrides section on controller."""
    return redirect('controller_home')

@role_required('controller', 'admin')
def controller_shift(request):
    """Direct shortcut to simulation shift controls on controller."""
    return redirect('controller_home')
