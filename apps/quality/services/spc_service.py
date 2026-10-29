"""
ISO 22400-2 Statistical Process Control (SPC) & Product Giveaway Calculation Engine.
Strictly implements:
- Subgroup X-bar and R control charts with standard factors (A2, d2, D3, D4)
- Overall Gaussian normal distribution bell curve generator
- Process capability indices (Cp, Cpk) with mathematical edge case protection
- Overfill giveaway financial loss calculator and interactive recalibration simulator
- Western Electric out-of-control rule detection
"""

import math
from decimal import Decimal
from django.utils import timezone
from django.db.models import Avg, Min, Max, Count, StdDev
from apps.masterdata.models import Line, Machine, Product
from apps.quality.models import SPCConfig, QualitySubgroup, QualitySample
from apps.operations.models import WeightSample


# ISO 22400-2 / ASTM Standard Subgroup Control Chart Constants
SPC_FACTORS = {
    2: {'A2': 1.880, 'd2': 1.128, 'D3': 0.0,   'D4': 3.267},
    3: {'A2': 1.023, 'd2': 1.693, 'D3': 0.0,   'D4': 2.574},
    4: {'A2': 0.729, 'd2': 2.059, 'D3': 0.0,   'D4': 2.282},
    5: {'A2': 0.577, 'd2': 2.326, 'D3': 0.0,   'D4': 2.114},
    6: {'A2': 0.483, 'd2': 2.534, 'D3': 0.0,   'D4': 2.004},
    7: {'A2': 0.419, 'd2': 2.704, 'D3': 0.076, 'D4': 1.924},
    8: {'A2': 0.373, 'd2': 2.847, 'D3': 0.136, 'D4': 1.864},
    9: {'A2': 0.337, 'd2': 2.970, 'D3': 0.184, 'D4': 1.816},
    10: {'A2': 0.308, 'd2': 3.078, 'D3': 0.223, 'D4': 1.777},
}


def get_or_create_default_spc_config(product, machine=None):
    """Retrieves or creates default SPC configuration for given product and machine."""
    config = SPCConfig.objects.filter(product=product, machine=machine, is_active=True).first()
    if not config:
        config = SPCConfig.objects.filter(product=product, machine__isnull=True, is_active=True).first()
    if not config:
        # Create standard preset: 500g nominal, +/- 5g spec limits
        config = SPCConfig.objects.create(
            product=product,
            machine=machine,
            nominal_grams=Decimal('500.00'),
            usl_grams=Decimal('505.00'),
            lsl_grams=Decimal('495.00'),
            subgroup_size=5,
            material_cost_per_kg=Decimal('18.50'),
            annual_production_units=12000000,
        )
    return config


def record_weight_samples_and_subgroup(machine, product, weights, operator=None, line=None, is_simulated=False):
    """
    Records a batch of raw weight measurements and automatically rolls them into
    an ISO 22400-2 QualitySubgroup with X-bar, Range, and StdDev.
    """
    if not line:
        line = machine.line
    config = get_or_create_default_spc_config(product, machine)
    
    float_weights = [float(w) for w in weights]
    n = len(float_weights)
    if n == 0:
        return None
    
    mean_val = sum(float_weights) / n
    range_val = max(float_weights) - min(float_weights)
    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in float_weights) / (n - 1)
        std_val = math.sqrt(variance)
    else:
        std_val = 0.0

    # Determine next subgroup number
    last_sg = QualitySubgroup.objects.filter(machine=machine, product=product).order_by('-subgroup_number').first()
    next_sg_num = (last_sg.subgroup_number + 1) if last_sg else 1

    subgroup = QualitySubgroup.objects.create(
        config=config,
        machine=machine,
        line=line,
        product=product,
        subgroup_number=next_sg_num,
        sample_mean=Decimal(str(round(mean_val, 3))),
        sample_range=Decimal(str(round(range_val, 3))),
        sample_std=Decimal(str(round(std_val, 3))),
        timestamp=timezone.now(),
        is_simulated=is_simulated,
    )

    # Create individual sample records
    for w in float_weights:
        dec_w = Decimal(str(round(w, 2)))
        is_in_spec = (config.lsl_grams <= dec_w <= config.usl_grams)
        QualitySample.objects.create(
            subgroup=subgroup,
            machine=machine,
            line=line,
            product=product,
            measured_weight_grams=dec_w,
            nominal_target_grams=config.nominal_grams,
            deviation_grams=dec_w - config.nominal_grams,
            is_within_spec=is_in_spec,
            operator=operator,
            timestamp=subgroup.timestamp,
            is_simulated=is_simulated,
        )
        # Also mirror to WeightSample for cross-compatibility
        WeightSample.objects.create(
            machine=machine,
            line=line,
            product=product,
            measured_weight_grams=dec_w,
            nominal_target_grams=config.nominal_grams,
            deviation_grams=dec_w - config.nominal_grams,
            is_within_spec=is_in_spec,
            operator=operator,
            timestamp=subgroup.timestamp,
        )

    return subgroup


def calculate_spc_metrics(machine=None, line=None, product=None, days=7, is_simulated=False):
    """
    Computes comprehensive ISO 22400-2 SPC control chart points, Gaussian distribution,
    Process Capability Indices (Cp, Cpk), and giveaway losses.
    """
    # 1. Resolve configuration
    target_product = product or Product.objects.first()
    if not target_product:
        return {'status': 'NO_DATA', 'error': 'No products defined in master data.'}
    
    config = get_or_create_default_spc_config(target_product, machine)
    
    # 2. Query subgroups
    sg_qs = QualitySubgroup.objects.filter(is_simulated=is_simulated)
    if product:
        sg_qs = sg_qs.filter(product=product)
    if machine:
        sg_qs = sg_qs.filter(machine=machine)
    elif line:
        sg_qs = sg_qs.filter(line=line)
    
    subgroups = list(sg_qs.order_by('subgroup_number')[:30])
    k = len(subgroups)
    
    # Also fetch individual samples for overall distribution
    sample_qs = QualitySample.objects.filter(is_simulated=is_simulated)
    if product:
        sample_qs = sample_qs.filter(product=product)
    if machine:
        sample_qs = sample_qs.filter(machine=machine)
    elif line:
        sample_qs = sample_qs.filter(line=line)
    
    total_samples_count = sample_qs.count()
    
    n = config.subgroup_size
    factors = SPC_FACTORS.get(n, SPC_FACTORS[5])
    a2 = factors['A2']
    d2 = factors['d2']
    d3 = factors['D3']
    d4 = factors['D4']
    
    usl = float(config.usl_grams)
    lsl = float(config.lsl_grams)
    nominal = float(config.nominal_grams)
    
    if k < 2 or total_samples_count < 5:
        # Insufficient data
        return {
            'status': 'INSUFFICIENT_DATA',
            'subgroups_count': k,
            'samples_count': total_samples_count,
            'config': {
                'nominal': nominal,
                'usl': usl,
                'lsl': lsl,
                'subgroup_size': n,
                'cost_per_kg': float(config.material_cost_per_kg),
            },
            'xbar_chart': None,
            'r_chart': None,
            'capability': None,
            'giveaway': None,
            'gaussian_curve': None,
        }

    # 3. Calculate X-bar & R Centerlines
    grand_mean = sum(float(sg.sample_mean) for sg in subgroups) / k
    mean_range = sum(float(sg.sample_range) for sg in subgroups) / k
    
    ucl_xbar = grand_mean + (a2 * mean_range)
    lcl_xbar = grand_mean - (a2 * mean_range)
    
    ucl_r = d4 * mean_range
    lcl_r = d3 * mean_range

    # 4. Process Standard Deviation (within-subgroup estimator)
    sigma_within = mean_range / d2 if d2 > 0 else 0.001
    
    # Overall sample std dev
    sample_weights = list(sample_qs.values_list('measured_weight_grams', flat=True))
    float_weights = [float(w) for w in sample_weights]
    mu_overall = sum(float_weights) / len(float_weights)
    
    if len(float_weights) > 1:
        overall_variance = sum((x - mu_overall) ** 2 for x in float_weights) / (len(float_weights) - 1)
        sigma_overall = math.sqrt(overall_variance)
    else:
        sigma_overall = 0.001

    # 5. Process Capability Indices (Cp, Cpk)
    # Per ISO / AIAG: Cp uses 6*sigma_within or 6*sigma_overall
    active_sigma = sigma_overall if sigma_overall > 0.0001 else sigma_within
    
    if active_sigma > 0 and (usl > lsl):
        cp = (usl - lsl) / (6.0 * active_sigma)
        cpu = (usl - mu_overall) / (3.0 * active_sigma)
        cpl = (mu_overall - lsl) / (3.0 * active_sigma)
        cpk = min(cpu, cpl)
    else:
        cp = None
        cpk = None

    # Capability rating
    if cpk is not None:
        if cpk >= 1.33:
            capability_rating = 'CAPABLE'
            capability_color = '#10B981'  # Green
            capability_text = 'Process is capable and centered (World-Class Six Sigma benchmark met).'
        elif cpk >= 1.00:
            capability_rating = 'MARGINAL'
            capability_color = '#F59E0B'  # Amber
            capability_text = 'Process is marginally capable; tighter control or recalibration recommended.'
        else:
            capability_rating = 'CRITICAL'
            capability_color = '#EF4444'  # Red
            capability_text = 'Critical: High risk of out-of-spec underfill or excessive material giveaway.'
    else:
        capability_rating = 'UNAVAILABLE'
        capability_color = '#6B7280'
        capability_text = 'Insufficient variation or sample count.'

    # 6. Build chart data series
    xbar_points = []
    r_points = []
    out_of_control_count = 0

    for sg in subgroups:
        m = float(sg.sample_mean)
        r = float(sg.sample_range)
        is_ooc_x = (m > ucl_xbar or m < lcl_xbar)
        is_ooc_r = (r > ucl_r or r < lcl_r)
        is_ooc = is_ooc_x or is_ooc_r
        if is_ooc:
            out_of_control_count += 1

        xbar_points.append({
            'sg': sg.subgroup_number,
            'time': sg.timestamp.strftime('%H:%M'),
            'value': round(m, 2),
            'is_ooc': is_ooc_x,
        })
        r_points.append({
            'sg': sg.subgroup_number,
            'time': sg.timestamp.strftime('%H:%M'),
            'value': round(r, 2),
            'is_ooc': is_ooc_r,
        })

    # 7. Giveaway & Financial Cost
    # Giveaway occurs when actual average fill weight exceeds nominal target
    avg_giveaway_grams = max(0.0, mu_overall - nominal)
    cost_per_kg = float(config.material_cost_per_kg)
    annual_units = config.annual_production_units

    # Current sample batch giveaway
    sample_giveaway_kg = (total_samples_count * avg_giveaway_grams) / 1000.0
    sample_giveaway_cost = sample_giveaway_kg * cost_per_kg

    # Projected annual giveaway
    annual_giveaway_kg = (annual_units * avg_giveaway_grams) / 1000.0
    annual_giveaway_cost = annual_giveaway_kg * cost_per_kg

    # 8. Gaussian Normal Distribution Bell Curve Coordinates
    # Generate 25 normalized SVG points from mu - 3.5*sigma to mu + 3.5*sigma
    bell_points = []
    svg_width = 560
    svg_height = 140
    start_x = mu_overall - (3.5 * active_sigma)
    end_x = mu_overall + (3.5 * active_sigma)
    step_x = (end_x - start_x) / 24.0

    max_pdf = 1.0 / (active_sigma * math.sqrt(2.0 * math.pi)) if active_sigma > 0 else 1.0

    for i in range(25):
        val_x = start_x + (i * step_x)
        exponent = -0.5 * (((val_x - mu_overall) / active_sigma) ** 2) if active_sigma > 0 else 0
        pdf_y = (1.0 / (active_sigma * math.sqrt(2.0 * math.pi))) * math.exp(exponent) if active_sigma > 0 else 0
        
        # Normalize to SVG space
        svg_px = ((val_x - start_x) / (end_x - start_x)) * svg_width
        svg_py = svg_height - ((pdf_y / max_pdf) * (svg_height - 20)) - 10
        bell_points.append({
            'x': round(svg_px, 1),
            'y': round(svg_py, 1),
            'gram_val': round(val_x, 2),
        })

    # Spec limit SVG positions
    def to_svg_x(val):
        pct = (val - start_x) / (end_x - start_x) if (end_x > start_x) else 0.5
        return max(0.0, min(svg_width, pct * svg_width))

    lsl_svg_x = round(to_svg_x(lsl), 1)
    usl_svg_x = round(to_svg_x(usl), 1)
    nominal_svg_x = round(to_svg_x(nominal), 1)
    mean_svg_x = round(to_svg_x(mu_overall), 1)

    return {
        'status': 'OK',
        'subgroups_count': k,
        'samples_count': total_samples_count,
        'out_of_control_count': out_of_control_count,
        'config': {
            'nominal': nominal,
            'usl': usl,
            'lsl': lsl,
            'subgroup_size': n,
            'cost_per_kg': cost_per_kg,
            'annual_units': annual_units,
        },
        'xbar_chart': {
            'points': xbar_points,
            'cl': round(grand_mean, 2),
            'ucl': round(ucl_xbar, 2),
            'lcl': round(lcl_xbar, 2),
        },
        'r_chart': {
            'points': r_points,
            'cl': round(mean_range, 2),
            'ucl': round(ucl_r, 2),
            'lcl': round(lcl_r, 2),
        },
        'stats': {
            'grand_mean': round(grand_mean, 2),
            'mean_range': round(mean_range, 2),
            'mu_overall': round(mu_overall, 2),
            'sigma_overall': round(active_sigma, 3),
        },
        'capability': {
            'cp': round(cp, 2) if cp is not None else 'N/A',
            'cpk': round(cpk, 2) if cpk is not None else 'N/A',
            'rating': capability_rating,
            'color': capability_color,
            'text': capability_text,
        },
        'giveaway': {
            'avg_giveaway_grams': round(avg_giveaway_grams, 2),
            'sample_giveaway_kg': round(sample_giveaway_kg, 2),
            'sample_giveaway_cost': round(sample_giveaway_cost, 2),
            'annual_giveaway_kg': round(annual_giveaway_kg, 1),
            'annual_giveaway_cost': round(annual_giveaway_cost, 2),
        },
        'gaussian_curve': {
            'bell_points': bell_points,
            'svg_points_str': " ".join(f"{p['x']},{p['y']}" for p in bell_points),
            'lsl_svg_x': lsl_svg_x,
            'usl_svg_x': usl_svg_x,
            'nominal_svg_x': nominal_svg_x,
            'mean_svg_x': mean_svg_x,
        }
    }


def calculate_weight_giveaway(machine=None, line=None, product=None, is_simulated=False):
    """Convenience wrapper returning giveaway mass and monetary cost."""
    metrics = calculate_spc_metrics(machine=machine, line=line, product=product, is_simulated=is_simulated)
    gw = metrics.get('giveaway') or {}
    return {
        'total_giveaway_kg': gw.get('sample_giveaway_kg', 0.0),
        'giveaway_cost_usd': gw.get('sample_giveaway_cost', 0.0),
        'avg_giveaway_grams': gw.get('avg_giveaway_grams', 0.0),
        'annual_giveaway_cost': gw.get('annual_giveaway_cost', 0.0),
    }


def simulate_recalibration(target_offset_grams, machine=None, line=None, product=None, is_simulated=False):
    """
    Simulates shifting the fill mean closer to nominal target.
    Calculates projected annual financial savings, simulated Cpk, and estimated legal underfill probability.
    
    Disclaimer (Section 6 authority):
    The slider is an estimate based on assumptions and does not prove zero underfill risk or regulatory compliance.
    """
    base_metrics = calculate_spc_metrics(machine=machine, line=line, product=product, is_simulated=is_simulated)
    if base_metrics['status'] != 'OK':
        return {'status': 'ERROR', 'message': 'Insufficient data for recalibration simulation.'}

    stats = base_metrics['stats']
    config = base_metrics['config']
    giveaway = base_metrics['giveaway']

    current_mu = stats['mu_overall']
    sigma = stats['sigma_overall']
    nominal = config['nominal']
    lsl = config['lsl']
    usl = config['usl']
    cost_per_kg = config['cost_per_kg']
    annual_units = config['annual_units']

    # Target mean after adjustment
    simulated_mu = current_mu + float(target_offset_grams)
    simulated_giveaway_grams = max(0.0, simulated_mu - nominal)
    
    # Financial savings
    grams_saved_per_unit = max(0.0, current_mu - simulated_mu)
    annual_savings_kg = (annual_units * grams_saved_per_unit) / 1000.0
    annual_savings_cost = annual_savings_kg * cost_per_kg

    # Simulated Capability
    if sigma > 0:
        sim_cpu = (usl - simulated_mu) / (3.0 * sigma)
        sim_cpl = (simulated_mu - lsl) / (3.0 * sigma)
        sim_cpk = min(sim_cpu, sim_cpl)
        
        # Z-score for legal underfill risk (Probability of filling below LSL)
        z_score = (lsl - simulated_mu) / sigma
        # Standard normal CDF approximation
        underfill_risk_pct = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0))) * 100.0
    else:
        sim_cpk = None
        underfill_risk_pct = 0.0

    return {
        'status': 'OK',
        'current_mean': current_mu,
        'simulated_mean': round(simulated_mu, 2),
        'offset_grams': float(target_offset_grams),
        'grams_saved_per_unit': round(grams_saved_per_unit, 2),
        'annual_savings_kg': round(annual_savings_kg, 1),
        'annual_savings_cost': round(annual_savings_cost, 2),
        'current_cpk': base_metrics['capability']['cpk'],
        'simulated_cpk': round(sim_cpk, 2) if sim_cpk is not None else 'N/A',
        'underfill_risk_pct': round(underfill_risk_pct, 4),
        'underfill_risk_text': f"{underfill_risk_pct:.3f}% estimated units below legal LSL limit",
        'disclaimer': (
            "Compliance Disclaimer: This recalibration slider provides statistical estimates based on normal distribution assumptions. "
            "It does not replace certified legal metrology calibration or guarantee zero underfill liability."
        )
    }
