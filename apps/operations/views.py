"""
Shop-Floor Operations, Maintenance & Operator Console Views.
Strictly implements:
- F05: Operator Touch Console (Glove-friendly, classification, scrap numpad, scale weight, maintenance call)
- F06: Stoppages Intelligence & SMED 4-Phase Changeover Stopwatch
- F15: Live Floor Matrix & Guided Shift Handover Wizard
- F16: Maintenance Kanban Incident Lifecycle & Force-Lockout Release
"""

import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from apps.accounts.decorators import role_required
from apps.masterdata.models import Line, Machine, Product, Shift, ReasonCategory, StoppageReason, DefectReason
from apps.telemetry.models import MachineCurrentState, DowntimeEvent
from apps.telemetry.services.oee_engine import calculate_line_oee
from apps.telemetry.services.losses_engine import calculate_tpm_six_big_losses
from apps.telemetry.services.state_machine import ingest_telemetry_reading
from apps.operations.models import (
    MaintenanceTicket, SparePart, SparePartRequisition, ChangeoverEvent,
    DefectLog, WeightSample, ShiftHandover
)
from apps.operations.services.stoppage_service import (
    classify_stoppage_event, split_stoppage_event, calculate_juran_pareto, calculate_reliability_metrics
)
from apps.operations.services.maintenance_service import (
    is_machine_locked_by_maintenance, get_active_machine_lock_ticket,
    create_operator_maintenance_call, cancel_operator_maintenance_call,
    technician_clock_in, request_spare_part_for_ticket, deliver_spare_part_and_resume,
    transition_ticket_stage, resolve_and_release_machine
)
from apps.operations.services.smed_service import start_smed_changeover, advance_smed_phase
from apps.operations.services.shift_service import get_or_create_shift_handover, submit_and_lock_shift_handover


# ==============================================================================
# 1. Operator Touch Console (F05)
# ==============================================================================

@role_required('operator', 'supervisor', 'admin')
def operator_console_view(request):
    """
    Operator Touch Console HMI (/operator/).
    Features touch-friendly targets, flow tabs across line machines,
    large counters, classification modal, scrap numpad, and maintenance call.
    """
    lines = Line.objects.prefetch_related('machines').all()
    active_line_code = request.GET.get('line')
    selected_line = lines.filter(code=active_line_code).first() if active_line_code else lines.first()

    machines = selected_line.machines.all().order_by('sequence_order') if selected_line else []
    active_machine_code = request.GET.get('machine')
    selected_machine = None
    if active_machine_code:
        selected_machine = machines.filter(code=active_machine_code).first()
    if not selected_machine:
        selected_machine = selected_line.bottleneck_machine if selected_line and selected_line.bottleneck_machine else (machines.first() if machines else None)

    current_state = None
    is_locked = False
    is_locked_safety = False
    lock_ticket = None
    open_downtime_event = None
    active_call_ticket = None
    kiosk_check = {'allowed': True, 'conflict': False, 'locked_out': False, 'message': ''}

    if selected_machine:
        from apps.accounts.services.kiosk_service import (
            check_kiosk_exclusivity, claim_operator_session, check_machine_force_logout
        )
        current_state, _ = MachineCurrentState.objects.get_or_create(
            machine=selected_machine,
            defaults={'state_code': 'RUNNING', 'current_speed_cpm': selected_machine.ideal_run_rate_cpm}
        )
        is_locked_maint = is_machine_locked_by_maintenance(selected_machine)
        is_locked_safety, safety_reason = check_machine_force_logout(selected_machine)
        is_locked = is_locked_maint or is_locked_safety

        lock_ticket = get_active_machine_lock_ticket(selected_machine)
        open_downtime_event = DowntimeEvent.objects.filter(
            machine=selected_machine, end_time__isnull=True
        ).order_by('-start_time').first()
        active_call_ticket = MaintenanceTicket.objects.filter(
            machine=selected_machine, is_operator_call=True, status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
        ).first()

        # Kiosk session exclusivity check
        kiosk_check = check_kiosk_exclusivity(request.user, selected_machine, request.session.session_key)
        if kiosk_check['allowed'] and getattr(request, 'active_role', None) == 'operator':
            claim_operator_session(request.user, selected_machine, request.session.session_key)

    categories = ReasonCategory.objects.prefetch_related('reasons').all()
    defect_reasons = DefectReason.objects.all()
    recent_defects = DefectLog.objects.filter(machine=selected_machine).order_by('-timestamp')[:5] if selected_machine else []
    recent_weights = WeightSample.objects.filter(machine=selected_machine).order_by('-timestamp')[:5] if selected_machine else []

    context = {
        'lines': lines,
        'selected_line': selected_line,
        'machines': machines,
        'selected_machine': selected_machine,
        'curr': current_state,
        'is_locked': is_locked,
        'is_locked_safety': is_locked_safety,
        'lock_ticket': lock_ticket,
        'open_event': open_downtime_event,
        'active_call_ticket': active_call_ticket,
        'categories': categories,
        'defect_reasons': defect_reasons,
        'recent_defects': recent_defects,
        'recent_weights': recent_weights,
        'kiosk_check': kiosk_check,
        'kiosk_conflict': kiosk_check.get('conflict', False),
        'kiosk_locked_out': is_locked_safety or kiosk_check.get('locked_out', False),
        'kiosk_message': kiosk_check.get('message', ''),
    }
    return render(request, 'portal/operator_home.html', context)


@role_required('operator', 'supervisor', 'admin')
@require_POST
def operator_increment_count_action(request):
    """Quick +1, +5, +10 piece tap on operator console."""
    machine_id = request.POST.get('machine_id')
    machine = get_object_or_404(Machine, id=machine_id)

    # Check lock and session exclusivity
    from apps.accounts.services.kiosk_service import check_machine_force_logout, check_kiosk_exclusivity
    is_locked_safety, safety_msg = check_machine_force_logout(machine)
    if is_machine_locked_by_maintenance(machine) or is_locked_safety:
        messages.error(request, f"Machine {machine.code} is locked out ({safety_msg or 'Maintenance'}). Piece input is blocked.")
        return redirect(f"/operator/?machine={machine.code}")

    kiosk_check = check_kiosk_exclusivity(request.user, machine, request.session.session_key)
    if not kiosk_check['allowed']:
        messages.error(request, kiosk_check['message'])
        return redirect(f"/operator/?machine={machine.code}")

    increment = int(request.POST.get('increment', 1))
    ingest_telemetry_reading(
        machine=machine,
        pulse_count=increment,
        instant_cpm=machine.ideal_run_rate_cpm,
        state_code='RUNNING'
    )
    messages.success(request, f"+{increment} units logged successfully.")
    return redirect(f"/operator/?machine={machine.code}")


@role_required('operator', 'supervisor', 'admin')
@require_POST
def operator_classify_action(request):
    """1-Touch 2-level stoppage classification modal submission."""
    event_id = request.POST.get('event_id')
    category_id = request.POST.get('category_id')
    reason_id = request.POST.get('reason_id') or None
    notes = request.POST.get('notes', '')

    event = classify_stoppage_event(
        event_id=event_id,
        category_id=category_id,
        reason_id=reason_id,
        notes=notes,
        classified_by=request.user
    )
    category_name = event.category.name if event.category else 'Uncategorized'
    messages.success(request, f"Stoppage #{str(event.id)[:8]} classified as '{category_name}'.")
    return redirect(f"/operator/?machine={event.machine.code}")


@role_required('operator', 'supervisor', 'admin')
@require_POST
def operator_split_action(request):
    """Splits an active or historical stoppage into two non-overlapping intervals."""
    event_id = request.POST.get('event_id')
    split_seconds = int(request.POST.get('split_seconds', 0))
    reason_id_1 = request.POST.get('reason_id_1') or None
    reason_id_2 = request.POST.get('reason_id_2') or None
    notes_1 = request.POST.get('notes_1', '')
    notes_2 = request.POST.get('notes_2', '')

    try:
        e1, e2 = split_stoppage_event(
            event_id=event_id,
            split_seconds=split_seconds,
            reason_id_1=reason_id_1,
            reason_id_2=reason_id_2,
            notes_1=notes_1,
            notes_2=notes_2,
            user=request.user
        )
        messages.success(request, f"Stoppage split into two intervals: {e1.duration_seconds}s and {e2.duration_seconds}s.")
        return redirect(f"/operator/?machine={e1.machine.code}")
    except Exception as ex:
        messages.error(request, f"Could not split stoppage: {ex}")
        return redirect('/operator/')


@role_required('operator', 'supervisor', 'quality', 'admin')
@require_POST
def operator_scrap_action(request):
    """Logs scrap defect quantity via on-screen touch numpad."""
    machine_id = request.POST.get('machine_id')
    machine = get_object_or_404(Machine, id=machine_id)

    # Check lock and session exclusivity
    from apps.accounts.services.kiosk_service import check_machine_force_logout, check_kiosk_exclusivity
    is_locked_safety, safety_msg = check_machine_force_logout(machine)
    if is_machine_locked_by_maintenance(machine) or is_locked_safety:
        messages.error(request, f"Machine {machine.code} is locked out ({safety_msg or 'Maintenance'}). Scrap input is blocked.")
        return redirect(f"/operator/?machine={machine.code}")

    kiosk_check = check_kiosk_exclusivity(request.user, machine, request.session.session_key)
    if not kiosk_check['allowed']:
        messages.error(request, kiosk_check['message'])
        return redirect(f"/operator/?machine={machine.code}")

    reason_id = request.POST.get('reason_id')
    quantity = int(request.POST.get('quantity', 1))
    disposition = request.POST.get('disposition', 'SCRAP')
    notes = request.POST.get('notes', '')

    reason = get_object_or_404(DefectReason, id=reason_id) if reason_id else None

    # Record defect log
    DefectLog.objects.create(
        machine=machine,
        line=machine.line,
        shift=machine.line.factory.shifts.first(),
        product=machine.line.current_product,
        reason=reason,
        quantity=quantity,
        disposition=disposition,
        logged_by=request.user,
        notes=notes
    )

    # Increment machine current scrap count
    curr, _ = MachineCurrentState.objects.get_or_create(machine=machine)
    curr.shift_scrap_count += quantity
    curr.save(update_fields=['shift_scrap_count'])

    messages.warning(request, f"Logged {quantity}x defect pieces ({reason.name if reason else 'Scrap'}) as {disposition}.")
    return redirect(f"/operator/?machine={machine.code}")


@role_required('operator', 'supervisor', 'quality', 'admin')
@require_POST
def operator_weight_action(request):
    """Logs manual scale sample weight in grams."""
    machine_id = request.POST.get('machine_id')
    machine = get_object_or_404(Machine, id=machine_id)
    weight_grams = Decimal(request.POST.get('measured_weight_grams', '500.0'))

    sample = WeightSample.objects.create(
        machine=machine,
        line=machine.line,
        product=machine.line.current_product,
        shift=machine.line.factory.shifts.first(),
        measured_weight_grams=weight_grams,
        operator=request.user
    )

    status_str = "Within Spec" if sample.is_within_spec else "OUT OF SPECIFICATION"
    if sample.is_within_spec:
        messages.success(request, f"Scale sample: {weight_grams}g ({status_str}).")
    else:
        messages.error(request, f"Scale sample: {weight_grams}g is {status_str}! Check tolerances.")

    return redirect(f"/operator/?machine={machine.code}")


@role_required('operator', 'supervisor', 'admin')
@require_POST
def operator_call_maintenance_action(request):
    """Operator taps 'Call Maintenance' button on HMI."""
    machine_id = request.POST.get('machine_id')
    machine = get_object_or_404(Machine, id=machine_id)
    description = request.POST.get('description', 'Operator called maintenance technician from kiosk.')

    ticket = create_operator_maintenance_call(machine, request.user, description)
    messages.error(request, f"URGENT Maintenance Call dispatched: {ticket.ticket_number}. Machine force-lockout engaged.")
    return redirect(f"/operator/?machine={machine.code}")


@role_required('operator', 'supervisor', 'admin')
@require_POST
def operator_cancel_call_action(request):
    """Operator cancels unassigned maintenance call."""
    ticket_id = request.POST.get('ticket_id')
    cancelled = cancel_operator_maintenance_call(ticket_id, request.user)
    if cancelled:
        messages.info(request, "Maintenance call cancelled. Lockout cleared.")
    else:
        messages.error(request, "Cannot cancel call: technician already clocked in or ticket in progress.")
    return redirect('/operator/')


@role_required('operator', 'supervisor', 'admin')
@require_POST
def operator_session_release_action(request):
    """Operator releases active machine session."""
    from apps.accounts.services.kiosk_service import release_operator_session
    machine_id = request.POST.get('machine_id')
    machine = get_object_or_404(Machine, id=machine_id)
    released = release_operator_session(request.user, machine, supervisor_override=False)
    if released:
        messages.info(request, f"Kiosk session for machine {machine.code} released successfully.")
    else:
        messages.info(request, f"No active session found for machine {machine.code}.")
    return redirect(f"/operator/?machine={machine.code}")


@role_required('supervisor', 'admin')
@require_POST
def operator_session_override_action(request):
    """Supervisor overrides and releases a conflicting machine session."""
    from apps.accounts.services.kiosk_service import release_operator_session
    machine_id = request.POST.get('machine_id')
    machine = get_object_or_404(Machine, id=machine_id)
    release_operator_session(request.user, machine, supervisor_override=True)
    messages.warning(request, f"Supervisor override executed: Previous operator session on {machine.code} cleared.")
    return redirect(f"/operator/?machine={machine.code}")


# ==============================================================================
# 2. Floor Monitor & Shift Matrix (F15)
# ==============================================================================

@role_required('supervisor', 'manager', 'admin')
def floor_matrix_view(request):
    """
    Live Floor Matrix (/floor/).
    Displays 20-machine card grid, real-time status borders, line pacing,
    bottleneck constraint banner, and quick actions.
    """
    lines = Line.objects.prefetch_related('machines__kiosks').all()
    active_line_code = request.GET.get('line')
    selected_line = lines.filter(code=active_line_code).first() if active_line_code else lines.first()

    machines_data = []
    oee_data = None
    waterfall_data = None

    if selected_line:
        machines_qs = selected_line.machines.all().order_by('sequence_order')
        for m in machines_qs:
            curr, _ = MachineCurrentState.objects.get_or_create(
                machine=m,
                defaults={'state_code': 'RUNNING', 'current_speed_cpm': m.ideal_run_rate_cpm}
            )
            is_locked = is_machine_locked_by_maintenance(m)
            machines_data.append({
                'machine': m,
                'state': curr,
                'is_locked': is_locked,
                'lock_ticket': get_active_machine_lock_ticket(m) if is_locked else None,
            })

        oee_data = calculate_line_oee(selected_line)
        waterfall_data = calculate_tpm_six_big_losses(selected_line)

    open_tickets_count = MaintenanceTicket.objects.filter(
        status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'WAITING_SPARES', 'TESTING']
    ).count()

    context = {
        'lines': lines,
        'selected_line': selected_line,
        'machines_data': machines_data,
        'oee': oee_data,
        'waterfall': waterfall_data,
        'open_tickets_count': open_tickets_count,
    }
    return render(request, 'portal/floor_home.html', context)


# ==============================================================================
# 3. Stoppages Intelligence & SMED Changeovers (F06)
# ==============================================================================

@role_required('supervisor', 'maintenance', 'engineer', 'manager', 'admin')
def stoppages_hub_view(request):
    """
    Active Stoppages Registry & Juran 80/20 Pareto Analytics (/stoppages/).
    """
    lines = Line.objects.all()
    selected_line_code = request.GET.get('line')
    selected_line = lines.filter(code=selected_line_code).first() if selected_line_code else lines.first()

    # Active / Unclassified stoppage events
    active_events = DowntimeEvent.objects.filter(
        line=selected_line
    ).order_by('-start_time')[:30] if selected_line else []

    pareto_data = calculate_juran_pareto(line=selected_line, days=7)
    reliability = calculate_reliability_metrics(line=selected_line, days=7)
    categories = ReasonCategory.objects.prefetch_related('reasons').all()

    context = {
        'lines': lines,
        'selected_line': selected_line,
        'active_events': active_events,
        'pareto': pareto_data,
        'reliability': reliability,
        'categories': categories,
    }
    return render(request, 'portal/stoppages_home.html', context)


@role_required('supervisor', 'maintenance', 'engineer', 'manager', 'admin')
def stoppages_reliability_view(request):
    """Detailed reliability metrics view (/stoppages/reliability/)."""
    return stoppages_hub_view(request)


@role_required('supervisor', 'operator', 'maintenance', 'admin')
def smed_hub_view(request):
    """
    Digital SMED 4-Phase Changeover Stopwatch (/smed/).
    """
    lines = Line.objects.all()
    selected_line_code = request.GET.get('line')
    selected_line = lines.filter(code=selected_line_code).first() if selected_line_code else lines.first()

    active_changeover = None
    recent_changeovers = []
    products = Product.objects.all()

    if selected_line:
        active_changeover = ChangeoverEvent.objects.filter(
            line=selected_line, status='IN_PROGRESS'
        ).first()
        recent_changeovers = ChangeoverEvent.objects.filter(
            line=selected_line, status='COMPLETED'
        ).order_by('-completed_at')[:5]

    context = {
        'lines': lines,
        'selected_line': selected_line,
        'active_changeover': active_changeover,
        'recent_changeovers': recent_changeovers,
        'products': products,
    }
    return render(request, 'portal/smed_home.html', context)


@role_required('supervisor', 'operator', 'maintenance', 'admin')
@require_POST
def smed_start_action(request):
    """Initiates SMED changeover on the line."""
    line_id = request.POST.get('line_id')
    line = get_object_or_404(Line, id=line_id)
    to_product_id = request.POST.get('to_product_id')
    notes = request.POST.get('notes', '')

    co = start_smed_changeover(line, to_product_id, request.user, notes)
    messages.success(request, f"SMED Changeover started for {line.name} -> {co.to_product.name}. Phase 1 active.")
    return redirect(f"/smed/?line={line.code}")


@role_required('supervisor', 'operator', 'maintenance', 'admin')
@require_POST
def smed_next_phase_action(request):
    """Advances SMED changeover to the next phase."""
    changeover_id = request.POST.get('changeover_id')
    rampup_units = int(request.POST.get('rampup_units', 0))
    rampup_scrap = int(request.POST.get('rampup_scrap', 0))

    co = advance_smed_phase(changeover_id, rampup_units, rampup_scrap)
    if co.status == 'COMPLETED':
        messages.success(request, f"SMED Changeover completed in {co.total_duration_minutes} min (Variance: {co.variance_minutes:+0.1f}m).")
    else:
        messages.info(request, f"Advanced to Phase {co.current_phase}: {co.get_current_phase_display()}.")
    return redirect(f"/smed/?line={co.line.code}")


# ==============================================================================
# 4. Maintenance Operations Center (F16)
# ==============================================================================

@role_required('maintenance', 'supervisor', 'manager', 'admin')
def maintenance_hub_view(request):
    """
    5-Stage Kanban Incident Board (/maintenance/).
    Columns: Open -> Assigned -> In Progress -> Waiting Spares -> Resolved.
    """
    tickets_qs = MaintenanceTicket.objects.select_related(
        'machine', 'line', 'reported_by', 'assigned_to', 'root_cause_category'
    ).all().order_by('-priority', '-created_at')

    open_tickets = tickets_qs.filter(status='OPEN')
    assigned_tickets = tickets_qs.filter(status='ASSIGNED')
    in_progress_tickets = tickets_qs.filter(status='IN_PROGRESS')
    waiting_spares_tickets = tickets_qs.filter(status='WAITING_SPARES')
    resolved_tickets = tickets_qs.filter(status__in=['TESTING', 'RESOLVED'])[:15]

    spares = SparePart.objects.all()
    categories = ReasonCategory.objects.all()
    machines = Machine.objects.all().order_by('line', 'sequence_order')

    context = {
        'open_tickets': open_tickets,
        'assigned_tickets': assigned_tickets,
        'in_progress_tickets': in_progress_tickets,
        'waiting_spares_tickets': waiting_spares_tickets,
        'resolved_tickets': resolved_tickets,
        'spares': spares,
        'categories': categories,
        'machines': machines,
    }
    return render(request, 'portal/maintenance_home.html', context)


@role_required('maintenance', 'admin')
def maintenance_spares_view(request):
    """Spare parts inventory catalog (/maintenance/spares/)."""
    spares = SparePart.objects.all()
    requisitions = SparePartRequisition.objects.select_related('ticket', 'part', 'requested_by').all()[:20]
    return render(request, 'portal/maintenance_spares.html', {
        'spares': spares,
        'requisitions': requisitions,
    })


@role_required('maintenance', 'admin')
def maintenance_history_view(request):
    """Historical maintenance repairs audit log (/maintenance/history/)."""
    history_tickets = MaintenanceTicket.objects.filter(
        status__in=['RESOLVED', 'CLOSED']
    ).select_related('machine', 'line', 'reported_by', 'assigned_to', 'root_cause_category').order_by('-resolved_at')[:50]
    return render(request, 'portal/maintenance_history.html', {
        'tickets': history_tickets,
    })


@role_required('maintenance', 'supervisor', 'admin')
@require_POST
def maintenance_clock_in_action(request):
    """Technician clocks in to start repair on a ticket."""
    ticket_id = request.POST.get('ticket_id')
    ticket = technician_clock_in(ticket_id, request.user)
    messages.success(request, f"Clocked in on {ticket.ticket_number}. Status updated to IN PROGRESS.")
    return redirect('/maintenance/')


@role_required('maintenance', 'supervisor', 'admin')
@require_POST
def maintenance_request_spare_action(request):
    """Technician requests spare part, pausing SLA timer."""
    ticket_id = request.POST.get('ticket_id')
    part_id = request.POST.get('part_id')
    quantity = int(request.POST.get('quantity', 1))

    req = request_spare_part_for_ticket(ticket_id, part_id, quantity, request.user)
    messages.warning(request, f"Requested {quantity}x {req.part.name}. Ticket moved to WAITING FOR SPARES (SLA Paused).")
    return redirect('/maintenance/')


@role_required('maintenance', 'admin')
@require_POST
def maintenance_deliver_spare_action(request):
    """Warehouse issues requested spare part."""
    requisition_id = request.POST.get('requisition_id')
    req = deliver_spare_part_and_resume(requisition_id, request.user)
    messages.success(request, f"Spare part {req.part.part_number} delivered. Ticket resumed to IN PROGRESS.")
    return redirect('/maintenance/spares/')


@role_required('maintenance', 'supervisor', 'admin')
@require_POST
def maintenance_resolve_action(request):
    """Mandatory Root Cause & Solution before releasing machine to production."""
    ticket_id = request.POST.get('ticket_id')
    root_cause_notes = request.POST.get('root_cause_notes', '').strip()
    solution_notes = request.POST.get('solution_notes', '').strip()
    root_cause_category_id = request.POST.get('root_cause_category_id') or None
    parts_used = request.POST.get('parts_used', '')

    if not root_cause_notes or not solution_notes:
        messages.error(request, "Root cause notes and solution notes are mandatory before releasing machine.")
        return redirect('/maintenance/')

    ticket = resolve_and_release_machine(
        ticket_id=ticket_id,
        root_cause_notes=root_cause_notes,
        solution_notes=solution_notes,
        root_cause_category_id=root_cause_category_id,
        parts_used=parts_used,
        technician_user=request.user
    )
    messages.success(request, f"Ticket {ticket.ticket_number} RESOLVED. Machine {ticket.machine.code} force-lockout cleared and released to production!")
    return redirect('/maintenance/')


# ==============================================================================
# 5. Shift Schedules & Guided Handover (F15)
# ==============================================================================

@role_required('supervisor', 'planner', 'manager', 'admin')
def shifts_hub_view(request):
    """
    Shift Management & Guided 3-Step Handover Hub (/shifts/).
    """
    lines = Line.objects.all()
    selected_line_code = request.GET.get('line')
    selected_line = lines.filter(code=selected_line_code).first() if selected_line_code else lines.first()

    shifts = Shift.objects.prefetch_related('breaks').all()
    active_shift = shifts.first()

    handover = None
    recent_handovers = []

    if selected_line:
        handover = get_or_create_shift_handover(selected_line, active_shift)
        recent_handovers = ShiftHandover.objects.filter(
            line=selected_line, status='LOCKED'
        ).order_by('-date', '-signed_at')[:5]

    open_tickets = MaintenanceTicket.objects.filter(
        line=selected_line,
        status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'WAITING_SPARES', 'TESTING']
    ) if selected_line else []

    context = {
        'lines': lines,
        'selected_line': selected_line,
        'shifts': shifts,
        'active_shift': active_shift,
        'handover': handover,
        'recent_handovers': recent_handovers,
        'open_tickets': open_tickets,
    }
    return render(request, 'portal/shifts_home.html', context)


@role_required('supervisor', 'manager', 'admin')
@require_POST
def shift_handover_submit_action(request):
    """Submits and digitally locks the 3-step shift handover."""
    handover_id = request.POST.get('handover_id')
    production_summary = request.POST.get('production_summary', '')
    safety_incidents = request.POST.get('safety_incidents', 'Zero safety incidents reported during shift.')
    maintenance_notes = request.POST.get('maintenance_notes', '')
    quality_notes = request.POST.get('quality_notes', '')

    handover = submit_and_lock_shift_handover(
        handover_id=handover_id,
        outgoing_user=request.user,
        incoming_user=None,
        production_summary=production_summary,
        safety_incidents=safety_incidents,
        maintenance_notes=maintenance_notes,
        quality_notes=quality_notes
    )
    messages.success(request, f"Shift Handover for {handover.line.name} successfully verified, signed, and locked!")
    return redirect(f"/shifts/?line={handover.line.code}")
