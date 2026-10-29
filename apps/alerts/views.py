"""
Real-Time Alerts & Alarm Storm Engine Views.
Strictly implements:
- F08: Configurable Alert Rules & Industrial Alarm Center (/alerts/)
- Alarm Storm Deduplication & Cooldown Suppression
- Auto-Resolve Watchdog tracking telemetry recovery conditions
- Full Alert Lifecycle: ACTIVE -> ACKNOWLEDGED -> RESOLVED
- Direct escalation to formal MaintenanceTicket
- Global Notification Drawer endpoints
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from apps.accounts.decorators import role_required
from apps.masterdata.models import Line, Machine
from apps.alerts.models import AlertRule, AlertIncident, AlertSuppressionLog
from apps.alerts.services.alert_engine import (
    evaluate_alert_rules, auto_resolve_watchdog, acknowledge_alert,
    resolve_alert, escalate_to_maintenance_ticket, get_active_alerts_summary
)


@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alerts_hub_view(request):
    """
    Alerts Incident Center & Rules Hub (/alerts/).
    """
    # Run auto-resolve watchdog on page load to sync status with telemetry
    auto_resolve_watchdog()
    evaluate_alert_rules()

    lines = Line.objects.all()
    selected_line_id = request.GET.get('line')
    selected_status = request.GET.get('status', 'ACTIVE')
    selected_severity = request.GET.get('severity', '')

    line = Line.objects.filter(id=selected_line_id).first() if selected_line_id else None

    incidents_qs = AlertIncident.objects.all().select_related('machine', 'line', 'rule', 'spawned_ticket')
    if line:
        incidents_qs = incidents_qs.filter(line=line)
    if selected_severity:
        incidents_qs = incidents_qs.filter(severity=selected_severity)
    
    if selected_status == 'ACTIVE':
        incidents = incidents_qs.filter(status__in=['ACTIVE', 'ACKNOWLEDGED']).order_by('-first_triggered_at')
    elif selected_status == 'RESOLVED':
        incidents = incidents_qs.filter(status='RESOLVED').order_by('-resolved_at')[:50]
    else:
        incidents = incidents_qs.order_by('-first_triggered_at')[:50]

    rules = AlertRule.objects.all().select_related('line', 'machine')
    summary = get_active_alerts_summary(line=line)

    context = {
        'page_title': 'Real-Time Alerts & Alarm Storm Engine',
        'page_title_ar': 'مركز التنبيهات المباشرة ومحرك كبح عواصف الإنذار',
        'lines': lines,
        'selected_line': line,
        'selected_status': selected_status,
        'selected_severity': selected_severity,
        'incidents': incidents,
        'rules': rules,
        'summary': summary,
        'all_machines': Machine.objects.all(),
    }
    return render(request, 'portal/alerts_home.html', context)


@require_POST
@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alert_acknowledge_action(request, alert_id):
    """Marks an alert incident as ACKNOWLEDGED."""
    inc = acknowledge_alert(alert_id, request.user)
    messages.success(request, f"Alert #{str(inc.id)[:8]} acknowledged.")
    return redirect(request.META.get('HTTP_REFERER', 'alerts_home'))


@require_POST
@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alert_resolve_action(request, alert_id):
    """Manually marks an alert as RESOLVED."""
    note = request.POST.get('note', '')
    inc = resolve_alert(alert_id, user=request.user, note=note)
    messages.success(request, f"Alert #{str(inc.id)[:8]} manually resolved.")
    return redirect(request.META.get('HTTP_REFERER', 'alerts_home'))


@require_POST
@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alert_escalate_action(request, alert_id):
    """Spawns a formal MaintenanceTicket from an alert incident."""
    ticket = escalate_to_maintenance_ticket(alert_id, request.user)
    messages.success(request, f"Created Maintenance Ticket #{str(ticket.id)[:8]} ('{ticket.title}') from alert.")
    return redirect('maintenance_home')


@require_POST
@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alert_create_rule_action(request):
    """Creates a new configurable industrial alert rule."""
    name = request.POST.get('name', '').strip()
    name_ar = request.POST.get('name_ar', '').strip()
    scope = request.POST.get('scope', 'GLOBAL')
    rule_type = request.POST.get('rule_type', 'DOWNTIME_DURATION')
    severity = request.POST.get('severity', 'WARNING')
    threshold_val = Decimal(request.POST.get('threshold_value', '0.0'))
    duration_sec = int(request.POST.get('duration_seconds', '300'))
    cooldown_min = int(request.POST.get('cooldown_minutes', '10'))
    auto_resolve = request.POST.get('auto_resolve') == 'on'

    line_id = request.POST.get('line_id')
    machine_id = request.POST.get('machine_id')

    line = Line.objects.filter(id=line_id).first() if line_id else None
    machine = Machine.objects.filter(id=machine_id).first() if machine_id else None

    if name:
        AlertRule.objects.create(
            name=name,
            name_ar=name_ar,
            scope=scope,
            line=line,
            machine=machine,
            rule_type=rule_type,
            severity=severity,
            threshold_value=threshold_val,
            duration_seconds=duration_sec,
            cooldown_minutes=cooldown_min,
            auto_resolve=auto_resolve,
            is_active=True,
        )
        messages.success(request, f"Alert Rule '{name}' created successfully.")
    else:
        messages.error(request, "Rule name is required.")

    return redirect('alerts_home')


@require_POST
@role_required('supervisor', 'maintenance', 'quality', 'planner', 'manager', 'admin')
def alert_evaluate_now_action(request):
    """Manually triggers rule evaluation and auto-resolve watchdog."""
    resolved = auto_resolve_watchdog()
    triggered = evaluate_alert_rules()
    messages.info(request, f"Evaluated rules: {len(triggered)} triggered/updated, {len(resolved)} auto-resolved.")
    return redirect('alerts_home')


@require_GET
def alert_drawer_api(request):
    """
    Renders HTML fragment for global slide-out notification drawer.
    """
    summary = get_active_alerts_summary()
    return render(request, 'portal/partials/notification_drawer.html', {
        'summary': summary,
        'active_alerts': summary['recent_alerts'],
    })


@require_GET
def alert_unread_count_api(request):
    """
    Returns live unread alert count for navbar pill badge.
    """
    summary = get_active_alerts_summary()
    return JsonResponse({
        'total_active': summary['total_active'],
        'unacknowledged': summary['unacknowledged'],
        'critical_count': summary['critical_count'],
    })

