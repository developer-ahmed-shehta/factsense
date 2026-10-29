"""
TPM Six Big Losses Waterfall Engine & Downtime Financial Costing.
Strictly implements Section 6.3 & 6.4:
- TPM Six Big Losses Categories
- Downtime Minutes allocation
- Financial Loss Costing
"""

from django.db.models import Sum
from apps.telemetry.models import DowntimeEvent, MachineCurrentState


def calculate_tpm_six_big_losses(line, shift=None, is_simulated=False):
    """
    Allocates planned production minutes across the TPM Six Big Losses:
    1. Unplanned Breakdown (Availability)
    2. Setup & Adjustments (Availability)
    3. Idling & Minor Micro-Stops (Performance)
    4. Reduced Speed Loss (Performance)
    5. Process Scrap & Defects (Quality)
    6. Startup Yield Scrap (Quality)
    Plus Net Fully Productive Time.
    """
    bottleneck = line.bottleneck_machine or line.machines.first()
    planned_minutes = shift.planned_operating_minutes if shift else 450.0

    # Query downtime events for bottleneck
    events_qs = DowntimeEvent.objects.filter(
        machine=bottleneck,
        is_simulated=is_simulated
    )

    def get_minutes(tpm_type):
        sec = events_qs.filter(tpm_loss_type=tpm_type).aggregate(total=Sum('duration_seconds'))['total'] or 0
        return round(sec / 60.0, 1)

    breakdown_min = get_minutes('AVAILABILITY_BREAKDOWN')
    changeover_min = get_minutes('AVAILABILITY_CHANGEOVER')
    microstop_min = get_minutes('PERFORMANCE_MINOR_STOP')

    # Performance Speed Loss (difference between expected output at ideal CPM and actual speed)
    speed_loss_min = 0.0
    defect_min = 0.0
    startup_min = 0.0

    try:
        curr = bottleneck.current_state if bottleneck else None
        if curr and bottleneck:
            ideal_cpm = bottleneck.ideal_run_rate_cpm or 120.0
            actual_cpm = curr.current_speed_cpm
            if curr.state_code == 'RUNNING' and actual_cpm < ideal_cpm and actual_cpm > 0:
                # Speed loss in equivalent minutes
                speed_ratio = (ideal_cpm - actual_cpm) / ideal_cpm
                speed_loss_min = round(speed_ratio * 30.0, 1)  # scaled to shift interval

            # Quality scrap equivalent lost minutes
            # Lost minutes = scrap units / ideal CPM
            scrap_units = curr.shift_scrap_count
            if ideal_cpm > 0 and scrap_units > 0:
                defect_min = round(scrap_units / ideal_cpm, 1)
    except MachineCurrentState.DoesNotExist:
        pass

    total_losses_min = round(breakdown_min + changeover_min + microstop_min + speed_loss_min + defect_min + startup_min, 1)
    net_productive_min = max(0.0, round(planned_minutes - total_losses_min, 1))

    return {
        'planned_production_minutes': planned_minutes,
        'unplanned_breakdown_minutes': breakdown_min,
        'setup_adjustments_minutes': changeover_min,
        'minor_stoppages_minutes': microstop_min,
        'reduced_speed_minutes': speed_loss_min,
        'process_defects_minutes': defect_min,
        'startup_yield_minutes': startup_min,
        'total_losses_minutes': total_losses_min,
        'net_productive_minutes': net_productive_min,
        'categories': [
            {'key': 'breakdown', 'label': '1. Unplanned Breakdown', 'minutes': breakdown_min, 'bucket': 'Availability', 'color': '#EF4444'},
            {'key': 'changeover', 'label': '2. Setup & Adjustments', 'minutes': changeover_min, 'bucket': 'Availability', 'color': '#F59E0B'},
            {'key': 'microstops', 'label': '3. Idling & Minor Stops', 'minutes': microstop_min, 'bucket': 'Performance', 'color': '#F97316'},
            {'key': 'speed_loss', 'label': '4. Reduced Speed Loss', 'minutes': speed_loss_min, 'bucket': 'Performance', 'color': '#EAB308'},
            {'key': 'defects', 'label': '5. Process Scrap & Defects', 'minutes': defect_min, 'bucket': 'Quality', 'color': '#EC4899'},
            {'key': 'startup', 'label': '6. Startup Yield Loss', 'minutes': startup_min, 'bucket': 'Quality', 'color': '#8B5CF6'},
            {'key': 'productive', 'label': 'Net Productive Operating Time', 'minutes': net_productive_min, 'bucket': 'Value-Added', 'color': '#10B981'},
        ]
    }


def calculate_financial_loss_cost(line, downtime_minutes, scrap_units=0, unit_profit=None, unit_scrap_cost=None):
    """
    Computes total monetary downtime loss:
    Loss Cost = Downtime Minutes x (Bottleneck CPM x Unit Profit) + (Scrap Units x Unit Scrap Cost)
    """
    bottleneck = line.bottleneck_machine or line.machines.first()
    ideal_cpm = bottleneck.ideal_run_rate_cpm if bottleneck else 120.0

    # Get SKU financial parameters or defaults
    product = line.current_product
    profit_per_unit = unit_profit if unit_profit is not None else (float(product.unit_cost) * 0.35 if product else 0.85)
    cost_per_scrap = unit_scrap_cost if unit_scrap_cost is not None else (float(product.scrap_cost) if product else 1.20)

    # Opportunity Cost of lost production = downtime minutes * ideal CPM * unit profit
    opportunity_loss = downtime_minutes * ideal_cpm * profit_per_unit
    direct_scrap_loss = scrap_units * cost_per_scrap

    total_loss_cost = round(opportunity_loss + direct_scrap_loss, 2)
    currency = line.factory.currency if line.factory else 'EGP'

    return {
        'downtime_minutes': downtime_minutes,
        'scrap_units': scrap_units,
        'opportunity_loss': round(opportunity_loss, 2),
        'direct_scrap_loss': round(direct_scrap_loss, 2),
        'total_loss_cost': total_loss_cost,
        'currency': currency,
    }

