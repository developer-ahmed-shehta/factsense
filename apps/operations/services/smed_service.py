"""
Digital SMED (Single-Minute Exchange of Die) 4-Phase Changeover Engine.
Strictly implements Section 7.3:
- Phase 1: Line Clearance & CIP (Cleaning in Place)
- Phase 2: Mechanical Tooling Swap
- Phase 3: Recipe & Parameter Loading
- Phase 4: Test Run & Ramp-Up to Speed
- Digital stopwatch with target variance and ramp-up scrap tracking
"""

from django.utils import timezone
from apps.masterdata.models import Line, Product
from apps.operations.models import ChangeoverEvent
from apps.telemetry.services.state_machine import ingest_telemetry_reading


def start_smed_changeover(line, to_product_id, operator_user=None, notes=""):
    """
    Initiates a new SMED changeover on the line.
    Transitions line machines to CHANGEOVER state and starts Phase 1 stopwatch.
    """
    to_product = Product.objects.get(id=to_product_id)
    from_product = line.current_product
    now = timezone.now()

    event = ChangeoverEvent.objects.create(
        line=line,
        machine=line.bottleneck_machine,
        shift=line.factory.shifts.first(),
        from_product=from_product,
        to_product=to_product,
        status='IN_PROGRESS',
        current_phase=1,
        started_at=now,
        phase1_started_at=now,
        operator=operator_user,
        notes=notes,
    )

    # Set line machines to CHANGEOVER
    for m in line.machines.all():
        ingest_telemetry_reading(
            machine=m,
            pulse_count=0,
            instant_cpm=0.0,
            state_code='CHANGEOVER',
            is_simulated=getattr(line, 'is_simulated', False)
        )

    return event


def advance_smed_phase(changeover_id, rampup_units=0, rampup_scrap=0):
    """
    Advances SMED changeover to the next phase (1 -> 2 -> 3 -> 4 -> Complete).
    Records phase duration and updates machine setpoints.
    """
    co = ChangeoverEvent.objects.get(id=changeover_id)
    now = timezone.now()

    if co.current_phase == 1:
        # End Phase 1, Start Phase 2
        p1_start = co.phase1_started_at or co.started_at
        co.phase1_duration_seconds = max(1, int((now - p1_start).total_seconds()))
        co.current_phase = 2
        co.phase2_started_at = now

    elif co.current_phase == 2:
        # End Phase 2, Start Phase 3
        p2_start = co.phase2_started_at or now
        co.phase2_duration_seconds = max(1, int((now - p2_start).total_seconds()))
        co.current_phase = 3
        co.phase3_started_at = now

    elif co.current_phase == 3:
        # End Phase 3, Start Phase 4 (Test Run & Ramp-Up)
        p3_start = co.phase3_started_at or now
        co.phase3_duration_seconds = max(1, int((now - p3_start).total_seconds()))
        co.current_phase = 4
        co.phase4_started_at = now

    elif co.current_phase == 4:
        # Complete Changeover
        p4_start = co.phase4_started_at or now
        co.phase4_duration_seconds = max(1, int((now - p4_start).total_seconds()))
        co.status = 'COMPLETED'
        co.completed_at = now
        co.rampup_total_units = rampup_units
        co.rampup_scrap_units = rampup_scrap

        co.total_duration_seconds = (
            co.phase1_duration_seconds +
            co.phase2_duration_seconds +
            co.phase3_duration_seconds +
            co.phase4_duration_seconds
        )

        # Update line product to new SKU
        line = co.line
        line.current_product = co.to_product
        line.save()

        # Restore machines to RUNNING at new product rated CPM
        for m in line.machines.all():
            ingest_telemetry_reading(
                machine=m,
                pulse_count=1,
                instant_cpm=m.ideal_run_rate_cpm,
                state_code='RUNNING',
                is_simulated=getattr(line, 'is_simulated', False)
            )

    co.save()
    return co

