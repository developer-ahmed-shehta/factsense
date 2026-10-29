"""
Stoppage Intelligence & Reliability Engineering Analytics Service.
Strictly implements Section 7.3 & Section 6.3:
- 1-Touch 2-level stoppage classification
- Stoppage interval splitting
- Juran 80/20 Pareto distribution (by duration and by frequency)
- Industrial Reliability KPIs: MTBF, MTTR, MTTF, Failure Rate (lambda)
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count
from apps.telemetry.models import DowntimeEvent
from apps.masterdata.models import ReasonCategory, StoppageReason, Line, Machine
from apps.telemetry.services.oee_engine import calculate_line_oee


def classify_stoppage_event(event_id, category_id, reason_id=None, notes="", classified_by=None):
    """
    Classifies an unassigned DowntimeEvent with Category and Specific Reason.
    Maps TPM loss type and responsible department.
    """
    event = DowntimeEvent.objects.get(id=event_id)
    category = ReasonCategory.objects.get(id=category_id)
    reason = StoppageReason.objects.filter(id=reason_id).first() if reason_id else None

    event.category = category
    event.reason = reason
    event.is_classified = True
    event.tpm_loss_type = reason.tpm_loss_type if reason else 'AVAILABILITY_BREAKDOWN'
    event.is_planned = reason.is_planned if reason else False
    if notes:
        event.notes = f"{event.notes}\n{notes}".strip() if event.notes else notes
    if classified_by:
        event.classified_by = classified_by
    event.save()
    return event


def split_stoppage_event(event_id, split_seconds, reason_id_1=None, reason_id_2=None, notes_1="", notes_2="", user=None):
    """
    Splits a single downtime event into two consecutive non-overlapping intervals.
    Example: 45 min stop -> 15 min Mechanical Jam + 30 min Waiting for Technician.
    """
    orig = DowntimeEvent.objects.get(id=event_id)
    total_sec = orig.duration_seconds or int((orig.end_time or timezone.now() - orig.start_time).total_seconds())

    if split_seconds <= 0 or split_seconds >= total_sec:
        raise ValueError("Split seconds must be strictly between 0 and total event duration.")

    split_point = orig.start_time + timedelta(seconds=split_seconds)
    second_part_seconds = total_sec - split_seconds

    # Part 1: Update original event
    orig.end_time = split_point
    orig.duration_seconds = split_seconds
    if reason_id_1:
        r1 = StoppageReason.objects.get(id=reason_id_1)
        orig.reason = r1
        orig.category = r1.category
        orig.is_classified = True
        orig.tpm_loss_type = r1.tpm_loss_type
        orig.is_planned = r1.is_planned
    if notes_1:
        orig.notes = f"{orig.notes} [Part 1: {notes_1}]".strip()
    orig.save()

    # Part 2: Create new consecutive event
    part2 = DowntimeEvent.objects.create(
        machine=orig.machine,
        line=orig.line,
        shift=orig.shift,
        product=orig.product,
        state_code=orig.state_code,
        start_time=split_point,
        end_time=orig.start_time + timedelta(seconds=total_sec),
        duration_seconds=second_part_seconds,
        tpm_loss_type=orig.tpm_loss_type,
        is_planned=orig.is_planned,
        is_simulated=orig.is_simulated,
        notes=f"Split from #{str(orig.id)[:8]} [Part 2: {notes_2}]".strip(),
        classified_by=user,
    )
    if reason_id_2:
        r2 = StoppageReason.objects.get(id=reason_id_2)
        part2.reason = r2
        part2.category = r2.category
        part2.is_classified = True
        part2.tpm_loss_type = r2.tpm_loss_type
        part2.is_planned = r2.is_planned
        part2.save()

    return orig, part2


def calculate_juran_pareto(line=None, machine=None, days=7, is_simulated=False):
    """
    Computes Juran 80/20 Pareto distribution of downtime root causes.
    Returns:
    - by_duration: sorted descending by minutes, with cumulative percentage
    - by_frequency: sorted descending by incident count, with cumulative percentage
    - total_downtime_minutes
    - total_stoppage_count
    """
    cutoff = timezone.now() - timedelta(days=days)
    qs = DowntimeEvent.objects.filter(start_time__gte=cutoff, is_simulated=is_simulated)

    if line:
        qs = qs.filter(line=line)
    if machine:
        qs = qs.filter(machine=machine)

    # 1. By Duration
    duration_data = []
    # Group by category / reason
    grouped = qs.values(
        'reason__name', 'category__name'
    ).annotate(
        total_seconds=Sum('duration_seconds'),
        count=Count('id')
    ).order_by('-total_seconds')

    total_sec = sum(item['total_seconds'] or 0 for item in grouped)
    total_minutes = round(total_sec / 60.0, 1)
    total_count = sum(item['count'] for item in grouped)

    running_sum = 0
    for item in grouped:
        sec = item['total_seconds'] or 0
        minutes = round(sec / 60.0, 1)
        running_sum += sec
        cum_pct = round((running_sum / total_sec) * 100.0, 1) if total_sec > 0 else 0.0
        reason_label = item['reason__name'] or item['category__name'] or 'Unclassified Stoppage'
        duration_data.append({
            'label': reason_label,
            'category': item['category__name'] or 'Unassigned',
            'minutes': minutes,
            'count': item['count'],
            'cum_pct': cum_pct,
            'is_vital_few': cum_pct <= 80.0,
        })

    # 2. By Frequency
    grouped_freq = qs.values(
        'reason__name', 'category__name'
    ).annotate(
        count=Count('id'),
        total_seconds=Sum('duration_seconds')
    ).order_by('-count')

    freq_data = []
    running_count = 0
    for item in grouped_freq:
        c = item['count']
        running_count += c
        cum_pct = round((running_count / total_count) * 100.0, 1) if total_count > 0 else 0.0
        reason_label = item['reason__name'] or item['category__name'] or 'Unclassified Stoppage'
        freq_data.append({
            'label': reason_label,
            'category': item['category__name'] or 'Unassigned',
            'count': c,
            'minutes': round((item['total_seconds'] or 0) / 60.0, 1),
            'cum_pct': cum_pct,
            'is_vital_few': cum_pct <= 80.0,
        })

    return {
        'by_duration': duration_data,
        'by_frequency': freq_data,
        'total_downtime_minutes': total_minutes,
        'total_stoppage_count': total_count,
        'days': days,
    }


def calculate_reliability_metrics(line=None, machine=None, days=7, is_simulated=False):
    """
    Computes standard industrial reliability engineering KPIs:
    - Operating Minutes: Total planned time minus breakdown downtime
    - Breakdowns Count (N): Number of unplanned failure events
    - MTBF (Mean Time Between Failures) = Operating Minutes / N
    - MTTR (Mean Time To Repair) = Total Breakdown Minutes / N
    - MTTF (Mean Time To Failure) = Operating Minutes / (N)
    - Failure Rate (lambda) = 1 / MTBF (failures per operating hour)
    """
    cutoff = timezone.now() - timedelta(days=days)
    qs = DowntimeEvent.objects.filter(
        start_time__gte=cutoff,
        is_planned=False,
        tpm_loss_type='AVAILABILITY_BREAKDOWN',
        is_simulated=is_simulated
    )
    if line:
        qs = qs.filter(line=line)
    if machine:
        qs = qs.filter(machine=machine)

    breakdown_count = qs.count()
    total_breakdown_sec = qs.aggregate(total=Sum('duration_seconds'))['total'] or 0
    total_breakdown_minutes = round(total_breakdown_sec / 60.0, 1)

    # Operating time approximation (7 days * 8h shift * 60 min = 3360 min planned per week)
    planned_minutes = days * 450.0  # standard 1-shift baseline
    operating_minutes = max(0.0, planned_minutes - total_breakdown_minutes)

    if breakdown_count > 0:
        mtbf_minutes = round(operating_minutes / breakdown_count, 1)
        mttr_minutes = round(total_breakdown_minutes / breakdown_count, 1)
        mttf_minutes = round(operating_minutes / breakdown_count, 1)
        failure_rate_per_hour = round((breakdown_count / (operating_minutes / 60.0)), 3) if operating_minutes > 0 else 0.0
    else:
        mtbf_minutes = operating_minutes  # No failures = whole operating time
        mttr_minutes = 0.0
        mttf_minutes = operating_minutes
        failure_rate_per_hour = 0.0

    return {
        'planned_minutes': planned_minutes,
        'operating_minutes': operating_minutes,
        'breakdown_count': breakdown_count,
        'total_breakdown_minutes': total_breakdown_minutes,
        'mtbf_minutes': mtbf_minutes,
        'mtbf_hours': round(mtbf_minutes / 60.0, 1),
        'mttr_minutes': mttr_minutes,
        'mttf_minutes': mttf_minutes,
        'failure_rate_per_hour': failure_rate_per_hour,
    }

