"""
Real-Time Industrial Alert Rule Engine & Alarm Storm Deduplication Service.
Strictly implements:
- F08: Rule evaluation against telemetry, speed, state, quality, vibration, and temperature
- Cooldown suppression window preventing repeating alarms during major trips
- Deduplication counter for recurring incident consolidation
- Telemetry recovery auto-resolve watchdog
- Direct escalation to formal MaintenanceTicket
"""

from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.masterdata.models import Line, Machine
from apps.telemetry.models import MachineCurrentState, DowntimeEvent
from apps.operations.models import MaintenanceTicket, DefectLog
from apps.quality.models import QualitySample
from apps.alerts.models import AlertRule, AlertIncident, AlertSuppressionLog


def trigger_or_deduplicate_alert(machine, rule_type, severity, title, message,
                                rule=None, title_ar="", message_ar="", is_simulated=False):
    """
    Triggers an industrial alert or deduplicates it if an identical incident is already active
    within the rule's cooldown suppression window.
    Returns: (incident, is_new_incident: bool)
    """
    now = timezone.now()
    cooldown_minutes = rule.cooldown_minutes if rule else 10
    cooldown_threshold = now - timedelta(minutes=cooldown_minutes)

    # Check for an active or acknowledged incident for this machine and rule type
    existing = AlertIncident.objects.filter(
        machine=machine,
        rule_type=rule_type,
        status__in=['ACTIVE', 'ACKNOWLEDGED'],
        is_simulated=is_simulated,
    ).order_by('-last_triggered_at').first()

    if existing:
        # Alarm Storm Cooldown Window Active -> Deduplicate & Suppress
        existing.occurrences_count += 1
        existing.last_triggered_at = now
        # Escalate severity if incoming is CRITICAL and existing was WARNING
        if severity == 'CRITICAL' and existing.severity != 'CRITICAL':
            existing.severity = 'CRITICAL'
            existing.title = title
            existing.message = message
        existing.save()

        # Log suppression audit
        AlertSuppressionLog.objects.create(
            incident=existing,
            rule=rule,
            machine=machine,
            suppressed_at=now,
            reason=f"Deduplicated trigger #{existing.occurrences_count} within {cooldown_minutes}m suppression window."
        )
        return existing, False

    # Create new Incident
    incident = AlertIncident.objects.create(
        rule=rule,
        machine=machine,
        line=machine.line,
        rule_type=rule_type,
        severity=severity,
        title=title,
        title_ar=title_ar or title,
        message=message,
        message_ar=message_ar or message,
        status='ACTIVE',
        occurrences_count=1,
        first_triggered_at=now,
        last_triggered_at=now,
        is_simulated=is_simulated,
    )
    return incident, True


def evaluate_alert_rules(line=None, machine=None, is_simulated=False):
    """
    Evaluates active AlertRules against current factory telemetry and machine states.
    Returns list of triggered or updated incidents.
    """
    rules_qs = AlertRule.objects.filter(is_active=True)
    if line:
        rules_qs = rules_qs.filter(models.Q(line=line) | models.Q(scope='GLOBAL'))
    if machine:
        rules_qs = rules_qs.filter(models.Q(machine=machine) | models.Q(line=machine.line) | models.Q(scope='GLOBAL'))

    machines_to_check = [machine] if machine else (list(line.machines.all()) if line else list(Machine.objects.all()))
    triggered_incidents = []

    for m in machines_to_check:
        state_obj = MachineCurrentState.objects.filter(machine=m, is_simulated=is_simulated).first()
        if not state_obj:
            continue

        for rule in rules_qs:
            # Check rule scope applicability
            if rule.scope == 'MACHINE' and rule.machine_id != m.id:
                continue
            if rule.scope == 'LINE' and rule.line_id != m.line_id:
                continue

            # 1. DOWNTIME_DURATION
            if rule.rule_type == 'DOWNTIME_DURATION':
                if state_obj.state in ['UNPLANNED_DOWNTIME', 'BLOCKED', 'STARVED']:
                    time_in_state = (timezone.now() - state_obj.state_changed_at).total_seconds()
                    threshold_sec = rule.duration_seconds or (float(rule.threshold_value) * 60)
                    if time_in_state >= threshold_sec:
                        inc, created = trigger_or_deduplicate_alert(
                            machine=m,
                            rule_type=rule.rule_type,
                            severity=rule.severity,
                            title=f"Excessive Downtime on {m.name} ({m.code})",
                            title_ar=f"توقف مطول في {m.name_ar or m.name} ({m.code})",
                            message=f"Machine {m.code} has been stopped in {state_obj.state} for {int(time_in_state/60)} minutes (threshold: {int(threshold_sec/60)} min).",
                            message_ar=f"الماكينة {m.code} متوقفة في حالة {state_obj.state} لمدة {int(time_in_state/60)} دقيقة (الحد: {int(threshold_sec/60)} دقيقة).",
                            rule=rule,
                            is_simulated=is_simulated,
                        )
                        triggered_incidents.append(inc)

            # 2. LOW_SPEED
            elif rule.rule_type == 'LOW_SPEED':
                if state_obj.state == 'RUNNING' and m.ideal_cpm > 0:
                    pct_speed = (float(state_obj.current_cpm) / float(m.ideal_cpm)) * 100.0
                    threshold_pct = float(rule.threshold_value) if rule.threshold_value > 0 else 80.0
                    if pct_speed < threshold_pct:
                        inc, created = trigger_or_deduplicate_alert(
                            machine=m,
                            rule_type=rule.rule_type,
                            severity=rule.severity,
                            title=f"Speed Loss Warning on {m.name} ({m.code})",
                            title_ar=f"انخفاض سرعة التشغيل في {m.name_ar or m.name}",
                            message=f"Machine {m.code} running at {pct_speed:.1f}% of ideal speed ({state_obj.current_cpm} vs {m.ideal_cpm} CPM).",
                            message_ar=f"الماكينة {m.code} تعمل بسرعة {pct_speed:.1f}% من السرعة المقررة ({state_obj.current_cpm} مقابل {m.ideal_cpm} عبوة/د).",
                            rule=rule,
                            is_simulated=is_simulated,
                        )
                        triggered_incidents.append(inc)

            # 3. TEMPERATURE_HIGH
            elif rule.rule_type == 'TEMPERATURE_HIGH':
                temp = float(state_obj.current_temperature_c)
                threshold_temp = float(rule.threshold_value) if rule.threshold_value > 0 else 75.0
                if temp > threshold_temp:
                    inc, created = trigger_or_deduplicate_alert(
                        machine=m,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        title=f"Overheating Alert on {m.name} ({m.code})",
                        title_ar=f"ارتفاع حرارة الماكينة {m.name_ar or m.name}",
                        message=f"Operating temperature at {temp:.1f}°C exceeds safety threshold of {threshold_temp:.1f}°C.",
                        message_ar=f"درجة حرارة التشغيل {temp:.1f} م° تتجاوز حد الأمان المسموح {threshold_temp:.1f} م°.",
                        rule=rule,
                        is_simulated=is_simulated,
                    )
                    triggered_incidents.append(inc)

            # 4. VIBRATION_HIGH
            elif rule.rule_type == 'VIBRATION_HIGH':
                vib = float(state_obj.current_vibration_rms)
                threshold_vib = float(rule.threshold_value) if rule.threshold_value > 0 else 4.5
                if vib > threshold_vib:
                    inc, created = trigger_or_deduplicate_alert(
                        machine=m,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        title=f"Excessive Vibration RMS on {m.name} ({m.code})",
                        title_ar=f"اهتزازات ميكانيكية مفرطة في {m.name_ar or m.name}",
                        message=f"Vibration RMS reached {vib:.2f} mm/s (threshold: {threshold_vib:.2f} mm/s). Inspect mechanical drive/bearings.",
                        message_ar=f"بلغ معدل الاهتزاز {vib:.2f} مم/ث (الحد المسموح: {threshold_vib:.2f} مم/ث). يلزم فحص المحامل والمحاور.",
                        rule=rule,
                        is_simulated=is_simulated,
                    )
                    triggered_incidents.append(inc)

            # 5. WEIGHT_OUT_OF_SPEC
            elif rule.rule_type == 'WEIGHT_OUT_OF_SPEC':
                recent_samples = list(QualitySample.objects.filter(machine=m, is_simulated=is_simulated).order_by('-timestamp')[:3])
                if len(recent_samples) >= 2 and all(not s.is_within_spec for s in recent_samples[:2]):
                    inc, created = trigger_or_deduplicate_alert(
                        machine=m,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        title=f"Consecutive Weight Out-of-Spec on {m.name}",
                        title_ar=f"عينات وزن خارج المواصفة في {m.name_ar or m.name}",
                        message=f"Last 2 consecutive weight samples out of specification on {m.code}. Fill nozzle drift detected.",
                        message_ar=f"آخر عينتي وزن متتاليتين خارج حدود المواصفة في {m.code}. انحراف في فوهات التعبئة.",
                        rule=rule,
                        is_simulated=is_simulated,
                    )
                    triggered_incidents.append(inc)

    return triggered_incidents


def auto_resolve_watchdog(line=None, machine=None, is_simulated=False):
    """
    Automatically resolves active alerts when telemetry parameters recover.
    Strictly follows Section 6:
    'Auto-resolve using each rule's actual recovery condition, not merely RUNNING.'
    """
    active_incidents = AlertIncident.objects.filter(
        status__in=['ACTIVE', 'ACKNOWLEDGED'],
        is_simulated=is_simulated,
    )
    if machine:
        active_incidents = active_incidents.filter(machine=machine)
    elif line:
        active_incidents = active_incidents.filter(line=line)

    resolved_list = []
    now = timezone.now()

    for inc in active_incidents:
        m = inc.machine
        state_obj = MachineCurrentState.objects.filter(machine=m, is_simulated=is_simulated).first()
        if not state_obj:
            continue

        should_resolve = False
        reason = ""

        # 1. Downtime recovery: Machine is back RUNNING
        if inc.rule_type == 'DOWNTIME_DURATION':
            if state_obj.state == 'RUNNING':
                should_resolve = True
                reason = f"Telemetry recovered: Machine {m.code} resumed normal RUNNING state."

        # 2. Low speed recovery: Speed back above threshold
        elif inc.rule_type == 'LOW_SPEED':
            if m.ideal_cpm > 0 and state_obj.state == 'RUNNING':
                pct = (float(state_obj.current_cpm) / float(m.ideal_cpm)) * 100.0
                threshold = float(inc.rule.threshold_value) if inc.rule and inc.rule.threshold_value > 0 else 80.0
                if pct >= threshold:
                    should_resolve = True
                    reason = f"Telemetry recovered: Speed restored to {pct:.1f}% ({state_obj.current_cpm} CPM)."

        # 3. Temperature recovery: Dropped below threshold
        elif inc.rule_type == 'TEMPERATURE_HIGH':
            threshold = float(inc.rule.threshold_value) if inc.rule and inc.rule.threshold_value > 0 else 75.0
            if float(state_obj.current_temperature_c) <= (threshold - 2.0):  # 2°C hysteresis
                should_resolve = True
                reason = f"Telemetry recovered: Operating temperature cooled to {state_obj.current_temperature_c:.1f}°C."

        # 4. Vibration recovery: Dropped below threshold
        elif inc.rule_type == 'VIBRATION_HIGH':
            threshold = float(inc.rule.threshold_value) if inc.rule and inc.rule.threshold_value > 0 else 4.5
            if float(state_obj.current_vibration_rms) <= (threshold - 0.5):
                should_resolve = True
                reason = f"Telemetry recovered: Vibration RMS normalized to {state_obj.current_vibration_rms:.2f} mm/s."

        # 5. Weight recovery: Latest sample within spec
        elif inc.rule_type == 'WEIGHT_OUT_OF_SPEC':
            latest_s = QualitySample.objects.filter(machine=m, is_simulated=is_simulated).order_by('-timestamp').first()
            if latest_s and latest_s.is_within_spec:
                should_resolve = True
                reason = f"Quality sample verified: Latest weight ({latest_s.measured_weight_grams}g) is within specification."

        if should_resolve:
            inc.status = 'RESOLVED'
            inc.resolved_at = now
            inc.resolution_note = f"Auto-resolved by Telemetry Watchdog: {reason}"
            inc.save()
            resolved_list.append(inc)

    return resolved_list


def acknowledge_alert(alert_id, user):
    """Marks an active alert as ACKNOWLEDGED by user."""
    inc = AlertIncident.objects.get(id=alert_id)
    if inc.status == 'ACTIVE':
        inc.status = 'ACKNOWLEDGED'
        inc.acknowledged_at = timezone.now()
        inc.acknowledged_by = user
        inc.save()
    return inc


def resolve_alert(alert_id, user=None, note=""):
    """Manually marks an alert as RESOLVED."""
    inc = AlertIncident.objects.get(id=alert_id)
    inc.status = 'RESOLVED'
    inc.resolved_at = timezone.now()
    inc.resolved_by = user
    inc.resolution_note = note or "Manually resolved by user."
    inc.save()
    return inc


def escalate_to_maintenance_ticket(alert_id, user):
    """
    Spawns a formal MaintenanceTicket directly from an alert incident.
    Enforces ticket-to-alert binding.
    """
    inc = AlertIncident.objects.get(id=alert_id)
    if inc.spawned_ticket:
        return inc.spawned_ticket

    ticket_priority = 'CRITICAL' if inc.severity == 'CRITICAL' else ('HIGH' if inc.severity == 'WARNING' else 'MEDIUM')
    is_force_lock = (inc.severity == 'CRITICAL')

    with transaction.atomic():
        ticket_no = f"TKT-ALT-{timezone.now().strftime('%m%d%H%M%S')}"
        ticket = MaintenanceTicket.objects.create(
            ticket_number=ticket_no,
            machine=inc.machine,
            line=inc.line,
            title=f"Alert Escalation: {inc.title}",
            description=f"Escalated from Alert #{str(inc.id)[:8]}:\n{inc.message}\nOccurrences: {inc.occurrences_count}",
            priority=ticket_priority,
            status='OPEN',
            force_lockout=is_force_lock,
            reported_by=user,
        )
        inc.spawned_ticket = ticket
        if inc.status == 'ACTIVE':
            inc.status = 'ACKNOWLEDGED'
            inc.acknowledged_at = timezone.now()
            inc.acknowledged_by = user
        inc.save()

    return ticket


def get_active_alerts_summary(line=None, is_simulated=False):
    """Returns quick aggregate summary of active and unacknowledged alerts."""
    qs = AlertIncident.objects.filter(status__in=['ACTIVE', 'ACKNOWLEDGED'], is_simulated=is_simulated)
    if line:
        qs = qs.filter(line=line)

    total_active = qs.count()
    critical_count = qs.filter(severity='CRITICAL').count()
    warning_count = qs.filter(severity='WARNING').count()
    info_count = qs.filter(severity='INFO').count()
    unacknowledged = qs.filter(status='ACTIVE').count()

    top_alerts = list(qs.order_by('-first_triggered_at')[:8])

    return {
        'total_active': total_active,
        'unacknowledged': unacknowledged,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'info_count': info_count,
        'recent_alerts': top_alerts,
    }
