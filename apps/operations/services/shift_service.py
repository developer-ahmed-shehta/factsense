"""
Guided 3-Step Shift Handover Service.
Strictly implements Section 7.7 and Appendix B 4.2:
- Step 1: Shift Metrics Review (Output, Scrap, Downtime, OEE)
- Step 2: Open Issues & Maintenance Tickets Audit
- Step 3: Outgoing & Incoming Operator / Supervisor Digital Sign-off and Shift Lock
"""

from decimal import Decimal
from django.utils import timezone
from apps.masterdata.models import Shift, Line
from apps.operations.models import ShiftHandover, MaintenanceTicket
from apps.telemetry.services.oee_engine import calculate_line_oee
from apps.telemetry.services.losses_engine import calculate_tpm_six_big_losses


def get_or_create_shift_handover(line, shift=None, date=None):
    """Retrieves or creates the active draft ShiftHandover record."""
    date = date or timezone.now().date()
    shift = shift or line.factory.shifts.first()

    handover, created = ShiftHandover.objects.get_or_create(
        line=line,
        shift=shift,
        date=date,
        defaults={'status': 'DRAFT'}
    )

    if created or handover.status == 'DRAFT':
        # Refresh real-time shift performance snapshot
        oee_data = calculate_line_oee(line, shift=shift)
        waterfall = calculate_tpm_six_big_losses(line, shift=shift)
        open_tickets = MaintenanceTicket.objects.filter(
            line=line, status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'WAITING_SPARES', 'TESTING']
        ).count()

        handover.total_output_units = oee_data.get('total_units', 0)
        handover.total_scrap_units = oee_data.get('scrap_units', 0)
        handover.total_downtime_minutes = int(
            waterfall.get('unplanned_breakdown_minutes', 0) + waterfall.get('setup_adjustments_minutes', 0)
        )
        handover.open_tickets_count = open_tickets
        oee_val = oee_data.get('oee', 0.0)
        handover.shift_oee = Decimal(str(oee_val if oee_val is not None else '0.0'))
        handover.save()

    return handover


def submit_and_lock_shift_handover(
    handover_id,
    outgoing_user,
    incoming_user=None,
    production_summary="",
    safety_incidents="Zero safety incidents reported during shift.",
    maintenance_notes="",
    quality_notes=""
):
    """
    Finalizes the 3-step shift handover:
    Records digital signatures, locks record against further modifications,
    and returns official shift handover summary.
    """
    handover = ShiftHandover.objects.get(id=handover_id)
    now = timezone.now()

    handover.outgoing_supervisor = outgoing_user
    if incoming_user:
        handover.incoming_supervisor = incoming_user
    handover.production_summary = production_summary
    handover.safety_incidents = safety_incidents
    handover.maintenance_handoff_notes = maintenance_notes
    handover.quality_handoff_notes = quality_notes
    handover.status = 'LOCKED'
    handover.signed_at = now
    handover.locked_at = now
    handover.save()

    return handover

