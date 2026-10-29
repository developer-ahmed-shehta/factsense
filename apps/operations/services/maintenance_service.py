"""
Maintenance Operations & Kanban Repair Lifecycle Service.
Strictly implements Section 7.2, 7.3, and Appendix B 4.3:
- 5-Stage Kanban Incident Board (OPEN -> ASSIGNED -> IN_PROGRESS -> WAITING_SPARES -> TESTING -> RESOLVED)
- Machine Force-Lockout verification and release
- Mobile-friendly technician repair clock-in
- Spare parts requisition with SLA timer pausing
- Mandatory root cause and solution logging before machine release
"""

from django.utils import timezone
from apps.masterdata.models import Machine, ReasonCategory, StoppageReason
from apps.operations.models import MaintenanceTicket, SparePart, SparePartRequisition
from apps.telemetry.services.state_machine import ingest_telemetry_reading


def is_machine_locked_by_maintenance(machine):
    """
    Checks if a machine has an active maintenance ticket enforcing force-lockout.
    If True, the operator console cannot run and shows a blocking lockout overlay.
    """
    return MaintenanceTicket.objects.filter(
        machine=machine,
        force_lockout=True,
        status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'WAITING_SPARES', 'TESTING']
    ).exists()


def get_active_machine_lock_ticket(machine):
    """Returns the primary active locking ticket for a machine, if any."""
    return MaintenanceTicket.objects.filter(
        machine=machine,
        force_lockout=True,
        status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'WAITING_SPARES', 'TESTING']
    ).first()


def create_operator_maintenance_call(machine, operator_user, description="Operator called maintenance technician from kiosk."):
    """
    Operator taps 'Call Maintenance' button on HMI.
    Spawns an urgent MaintenanceTicket, flags force_lockout=True, and transitions machine state.
    """
    ticket = MaintenanceTicket.objects.create(
        machine=machine,
        line=machine.line,
        title=f"Breakdown Call: {machine.name}",
        description=description,
        priority='URGENT',
        status='OPEN',
        reported_by=operator_user,
        force_lockout=True,
        is_operator_call=True,
    )
    # Update machine state to UNPLANNED_DOWNTIME if not already stopped
    ingest_telemetry_reading(
        machine=machine,
        pulse_count=0,
        instant_cpm=0.0,
        state_code='UNPLANNED_DOWNTIME',
        is_simulated=getattr(machine.line, 'is_simulated', False)
    )
    return ticket


def cancel_operator_maintenance_call(ticket_id, operator_user):
    """
    Operator cancels an unassigned call if the stoppage was minor/resolved by the operator.
    Only permitted if ticket is still OPEN and unassigned.
    """
    ticket = MaintenanceTicket.objects.get(id=ticket_id)
    if ticket.status == 'OPEN' and not ticket.assigned_to:
        ticket.status = 'CLOSED'
        ticket.force_lockout = False
        ticket.solution_notes = f"Operator cancelled call at {timezone.now().strftime('%H:%M')} (Minor jam cleared by operator)."
        ticket.closed_at = timezone.now()
        ticket.save()
        return True
    return False


def technician_clock_in(ticket_id, technician_user):
    """
    Technician arrives at machine and clocks in to start repair.
    Sets work_started_at and transitions status to IN_PROGRESS.
    """
    ticket = MaintenanceTicket.objects.get(id=ticket_id)
    now = timezone.now()
    ticket.assigned_to = technician_user
    if not ticket.assigned_at:
        ticket.assigned_at = now
    ticket.work_started_at = now
    ticket.status = 'IN_PROGRESS'
    ticket.save()
    return ticket


def request_spare_part_for_ticket(ticket_id, part_id, quantity=1, user=None):
    """
    Technician requests spare parts, transitioning ticket to WAITING_SPARES.
    Pauses SLA timer and records waiting timestamp.
    """
    ticket = MaintenanceTicket.objects.get(id=ticket_id)
    part = SparePart.objects.get(id=part_id)

    req = SparePartRequisition.objects.create(
        ticket=ticket,
        part=part,
        quantity=quantity,
        status='REQUESTED',
        requested_by=user,
    )

    ticket.status = 'WAITING_SPARES'
    ticket.waiting_spares_started_at = timezone.now()
    ticket.save()
    return req


def deliver_spare_part_and_resume(requisition_id, warehouse_user=None):
    """
    Warehouse issues requested spare part. Deducts inventory and transitions ticket back to IN_PROGRESS.
    Calculates paused SLA duration.
    """
    req = SparePartRequisition.objects.get(id=requisition_id)
    ticket = req.ticket
    now = timezone.now()

    # Deduct inventory
    part = req.part
    part.in_stock_quantity = max(0, part.in_stock_quantity - req.quantity)
    part.save()

    req.status = 'ISSUED'
    req.issued_at = now
    req.save()

    # Calculate paused SLA seconds
    if ticket.waiting_spares_started_at:
        paused = int((now - ticket.waiting_spares_started_at).total_seconds())
        ticket.paused_sla_seconds += paused
        ticket.waiting_spares_started_at = None

    ticket.status = 'IN_PROGRESS'
    ticket.save()
    return req


def transition_ticket_stage(ticket_id, target_status, user=None):
    """
    Moves ticket along the Kanban workflow.
    Validates stage progression.
    """
    ticket = MaintenanceTicket.objects.get(id=ticket_id)
    valid_transitions = {
        'OPEN': ['ASSIGNED', 'IN_PROGRESS', 'CLOSED'],
        'ASSIGNED': ['IN_PROGRESS', 'OPEN'],
        'IN_PROGRESS': ['WAITING_SPARES', 'TESTING', 'RESOLVED'],
        'WAITING_SPARES': ['IN_PROGRESS'],
        'TESTING': ['IN_PROGRESS', 'RESOLVED'],
        'RESOLVED': ['CLOSED', 'IN_PROGRESS'],
        'CLOSED': [],
    }

    if target_status not in valid_transitions.get(ticket.status, []):
        raise ValueError(f"Invalid transition from {ticket.status} to {target_status}.")

    now = timezone.now()
    if target_status == 'ASSIGNED' and not ticket.assigned_at:
        ticket.assigned_at = now
    elif target_status == 'IN_PROGRESS' and not ticket.work_started_at:
        ticket.work_started_at = now
    elif target_status == 'TESTING':
        pass
    elif target_status == 'RESOLVED':
        ticket.resolved_at = now
    elif target_status == 'CLOSED':
        ticket.closed_at = now

    ticket.status = target_status
    ticket.save()
    return ticket


def resolve_and_release_machine(
    ticket_id,
    root_cause_notes,
    solution_notes,
    root_cause_category_id=None,
    root_cause_reason_id=None,
    parts_used="",
    technician_user=None
):
    """
    Mandatory Root Cause & Solution verification before releasing machine to production.
    Unlocks machine force-lockout and transitions machine back to RUNNING.
    """
    if not root_cause_notes or not solution_notes:
        raise ValueError("Root cause notes and solution notes are mandatory before releasing machine.")

    ticket = MaintenanceTicket.objects.get(id=ticket_id)
    now = timezone.now()

    ticket.root_cause_notes = root_cause_notes
    ticket.solution_notes = solution_notes
    ticket.parts_used_notes = parts_used
    if root_cause_category_id:
        ticket.root_cause_category = ReasonCategory.objects.get(id=root_cause_category_id)
    if root_cause_reason_id:
        ticket.root_cause_reason = StoppageReason.objects.get(id=root_cause_reason_id)

    ticket.status = 'RESOLVED'
    ticket.resolved_at = now
    ticket.force_lockout = False  # Release lock!
    ticket.save()

    # Re-evaluate machine current state: return to RUNNING
    m = ticket.machine
    ingest_telemetry_reading(
        machine=m,
        pulse_count=1,
        instant_cpm=m.ideal_run_rate_cpm,
        state_code='RUNNING',
        is_simulated=getattr(m.line, 'is_simulated', False)
    )

    return ticket

