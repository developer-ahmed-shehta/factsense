"""
ISO 22400 OEE Industrial Calculation Engine.
Strictly implements:
- Availability (A): Operating Time / Planned Production Time
- Performance (P): Total Units / (Operating Minutes x Ideal Bottleneck CPM)
- Quality (Q): Good Units / Total Units
- Bottleneck Cadence: Line throughput governed by the designated constraint machine
"""

from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from apps.masterdata.models import Line, Machine, Shift
from apps.telemetry.models import DowntimeEvent, MachineCurrentState


def calculate_line_oee(line, shift=None, start_time=None, end_time=None, is_simulated=False):
    """
    Computes ISO 22400 OEE metrics for a production line.
    Cadence is strictly anchored to the line's designated Bottleneck Machine.
    """
    # 1. Identify Bottleneck Machine
    bottleneck = line.bottleneck_machine
    if not bottleneck:
        # Fallback to critical machine or first machine
        bottleneck = line.machines.filter(criticality_rank='A').first() or line.machines.first()

    if not bottleneck:
        return {
            'line_code': line.code,
            'availability': None,
            'performance': None,
            'quality': None,
            'oee': None,
            'bottleneck_code': None,
            'reason': 'No assets configured on line.',
        }

    # 2. Determine Time Basis (Planned Production Time)
    if shift:
        planned_minutes = shift.planned_operating_minutes
    else:
        # Fallback to active factory shift or standard 8-hour window (450 min planned)
        active_shift = line.factory.shifts.first()
        planned_minutes = active_shift.planned_operating_minutes if active_shift else 450.0

    if planned_minutes <= 0:
        return {
            'line_code': line.code,
            'availability': None,
            'performance': None,
            'quality': None,
            'oee': None,
            'bottleneck_code': bottleneck.code,
            'reason': 'Planned production time is zero.',
        }

    # 3. Calculate Availability Loss on Bottleneck Machine
    # Availability Loss = Sum of durations of Unplanned Downtime + Changeovers
    loss_events = DowntimeEvent.objects.filter(
        machine=bottleneck,
        tpm_loss_type__in=['AVAILABILITY_BREAKDOWN', 'AVAILABILITY_CHANGEOVER'],
        is_simulated=is_simulated
    )
    if start_time:
        loss_events = loss_events.filter(start_time__gte=start_time)
    if end_time:
        loss_events = loss_events.filter(start_time__lte=end_time)

    avail_loss_seconds = loss_events.aggregate(total=Sum('duration_seconds'))['total'] or 0
    avail_loss_minutes = avail_loss_seconds / 60.0

    operating_minutes = max(0.0, planned_minutes - avail_loss_minutes)
    availability_pct = round((operating_minutes / planned_minutes) * 100.0, 1) if planned_minutes > 0 else 0.0
    availability_pct = min(100.0, max(0.0, availability_pct))

    # 4. Calculate Performance on Bottleneck Machine
    # Performance = Total Units / (Operating Minutes x Ideal CPM)
    try:
        curr = bottleneck.current_state
        total_units = curr.shift_pulse_count
        scrap_units = curr.shift_scrap_count
        good_units = max(0, total_units - scrap_units)
    except MachineCurrentState.DoesNotExist:
        total_units = 0
        scrap_units = 0
        good_units = 0

    ideal_cpm = bottleneck.ideal_run_rate_cpm or 120.0
    expected_units = operating_minutes * ideal_cpm

    perf_notice = None
    if operating_minutes <= 0 or expected_units <= 0:
        performance_pct = 0.0 if total_units == 0 else 100.0
    else:
        perf_val = (total_units / expected_units) * 100.0
        if perf_val > 100.0:
            perf_notice = "Performance exceeds 100% (speed override or benchmark under-rating)"
        performance_pct = round(perf_val, 1)

    # 5. Calculate Quality
    # Quality = Good Units / Total Units
    if total_units <= 0:
        quality_pct = 100.0  # Zero defects baseline when starting
    else:
        quality_pct = round((good_units / total_units) * 100.0, 1)
        quality_pct = min(100.0, max(0.0, quality_pct))

    # 6. Overall ISO 22400 OEE = A x P x Q
    # Clamp Performance to 100 for overall OEE computation per standard convention
    effective_perf = min(100.0, performance_pct)
    oee_pct = round((availability_pct * effective_perf * quality_pct) / 10000.0, 1)

    return {
        'line_code': line.code,
        'bottleneck_code': bottleneck.code,
        'planned_production_minutes': planned_minutes,
        'operating_minutes': round(operating_minutes, 1),
        'availability': availability_pct,
        'performance': performance_pct,
        'quality': quality_pct,
        'oee': oee_pct,
        'total_units': total_units,
        'good_units': good_units,
        'scrap_units': scrap_units,
        'ideal_cpm': ideal_cpm,
        'performance_notice': perf_notice,
        'is_bottleneck_governed': True,
    }

