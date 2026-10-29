"""
Industrial State Machine Engine & Telemetry Ingestion Processor.
Strictly implements Section 5:
- 8 Standardized States (RUNNING, UNPLANNED_DOWNTIME, PLANNED_DOWNTIME, CHANGEOVER, MICRO_STOP, BLOCKED, STARVED, NO_DATA)
- Automatic Watchdog pulse gap detection
- Discrete state interval (DowntimeEvent) lifecycle management
"""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from apps.masterdata.models import Machine, StoppageReason
from apps.telemetry.models import MachineCurrentState, TelemetryReading, DowntimeEvent

WATCHDOG_GAP_SECONDS = 180  # 3 minutes without pulses triggers automatic downtime
MICRO_STOP_MAX_SECONDS = 180


def ingest_telemetry_reading(
    machine,
    pulse_count=1,
    instant_cpm=None,
    state_code=None,
    vibration_rms=None,
    temperature_c=None,
    is_simulated=False,
    timestamp=None
):
    """
    Core telemetry processor:
    1. Records raw TelemetryReading.
    2. Evaluates state machine transitions across 8 canonical states.
    3. Opens/closes DowntimeEvent intervals with TPM loss mapping.
    4. Updates cached MachineCurrentState.
    """
    now = timestamp or timezone.now()

    # Determine instant CPM
    if instant_cpm is None:
        instant_cpm = machine.ideal_run_rate_cpm if state_code == 'RUNNING' else 0.0

    # Determine state code if not provided
    if state_code is None:
        if pulse_count > 0 or instant_cpm > 0:
            state_code = 'RUNNING'
        else:
            state_code = 'MICRO_STOP'

    with transaction.atomic():
        # 1. Record Raw Telemetry Reading
        reading = TelemetryReading.objects.create(
            machine=machine,
            timestamp=now,
            pulse_count=pulse_count,
            instant_cpm=instant_cpm,
            state_code=state_code,
            vibration_rms=vibration_rms if vibration_rms is not None else 0.8,
            temperature_c=temperature_c if temperature_c is not None else 42.0,
            is_simulated=is_simulated,
        )

        # 2. Retrieve or Initialize Machine Current State
        current_state, created = MachineCurrentState.objects.get_or_create(
            machine=machine,
            defaults={
                'state_code': state_code,
                'current_speed_cpm': instant_cpm,
                'vibration_rms': reading.vibration_rms,
                'temperature_c': reading.temperature_c,
                'is_simulated': is_simulated,
                'last_pulse_at': now if pulse_count > 0 else None,
                'last_state_change': now,
            }
        )

        old_state = current_state.state_code
        state_changed = (old_state != state_code)

        # 3. State Transition Handling & Interval Accounting
        if state_changed or (created and state_code != 'RUNNING'):
            current_state.state_code = state_code
            current_state.last_state_change = now

            # Close any active open DowntimeEvent on this machine
            active_events = DowntimeEvent.objects.filter(
                machine=machine,
                end_time__isnull=True,
                is_simulated=is_simulated
            )
            for ev in active_events:
                ev.close_interval(now)

            # If transitioning to a non-running state, open a new discrete event
            if state_code != 'RUNNING':
                tpm_loss = map_state_to_tpm_loss(state_code)
                DowntimeEvent.objects.create(
                    machine=machine,
                    line=machine.line,
                    shift=current_state.active_shift,
                    product=current_state.active_product or machine.line.current_product,
                    state_code=state_code,
                    start_time=now,
                    tpm_loss_type=tpm_loss,
                    is_planned=(state_code in ['PLANNED_DOWNTIME', 'CHANGEOVER']),
                    is_simulated=is_simulated,
                )

        # Update metrics and pulse counts
        current_state.current_speed_cpm = instant_cpm
        if vibration_rms is not None:
            current_state.vibration_rms = vibration_rms
        if temperature_c is not None:
            current_state.temperature_c = temperature_c

        if pulse_count > 0:
            current_state.shift_pulse_count += pulse_count
            current_state.shift_good_count += pulse_count
            current_state.last_pulse_at = now

        current_state.is_simulated = is_simulated
        current_state.save()

    return current_state


def map_state_to_tpm_loss(state_code):
    """Maps standardized state codes to TPM Six Big Losses categories."""
    mapping = {
        'UNPLANNED_DOWNTIME': 'AVAILABILITY_BREAKDOWN',
        'CHANGEOVER': 'AVAILABILITY_CHANGEOVER',
        'PLANNED_DOWNTIME': 'AVAILABILITY_CHANGEOVER',
        'MICRO_STOP': 'PERFORMANCE_MINOR_STOP',
        'BLOCKED': 'PERFORMANCE_MINOR_STOP',
        'STARVED': 'PERFORMANCE_MINOR_STOP',
        'NO_DATA': 'AVAILABILITY_BREAKDOWN',
    }
    return mapping.get(state_code, 'AVAILABILITY_BREAKDOWN')


def evaluate_watchdog_pulse_gap(machine, now=None, timeout_seconds=WATCHDOG_GAP_SECONDS):
    """
    Automatic Watchdog:
    Detects missing pulse gaps on running equipment. If no pulse is seen within
    timeout_seconds, transitions machine to UNPLANNED_DOWNTIME and opens an active event.
    """
    now = now or timezone.now()
    try:
        curr = machine.current_state
    except MachineCurrentState.DoesNotExist:
        return None

    if curr.state_code == 'RUNNING' and curr.last_pulse_at:
        gap = (now - curr.last_pulse_at).total_seconds()
        if gap >= timeout_seconds:
            # Automatic transition to UNPLANNED_DOWNTIME
            curr.state_code = 'UNPLANNED_DOWNTIME'
            curr.current_speed_cpm = 0.0
            curr.last_state_change = now
            curr.save(update_fields=['state_code', 'current_speed_cpm', 'last_state_change'])

            # Open DowntimeEvent
            DowntimeEvent.objects.create(
                machine=machine,
                line=machine.line,
                shift=curr.active_shift,
                product=curr.active_product or machine.line.current_product,
                state_code='UNPLANNED_DOWNTIME',
                start_time=curr.last_pulse_at + timedelta(seconds=timeout_seconds),
                tpm_loss_type='AVAILABILITY_BREAKDOWN',
                is_planned=False,
                is_simulated=curr.is_simulated,
                notes='Auto-opened by pulse watchdog timeout.',
            )
            return curr

    return curr

