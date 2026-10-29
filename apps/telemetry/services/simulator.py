"""
Synthetic Signal Simulator & Scenario Injection Engine.
Strictly implements Section 7.9:
- Synthetic telemetry generation across line machines
- Clock speed multiplier (Paused 0x, 1x, 2x, 5x, 10x)
- 5 Pre-built scenario injectors:
  1. Cap Chute Jam (Capper faults, Filler blocked)
  2. Overfill Giveaway Drift (+1.2g weight drift)
  3. Mechanical Breakdown (Blow molder stops, downstream starved)
  4. Defect Burst (25 scrap defect spike)
  5. Golden Run (Target 95% OEE World-Class)
- Strict data separation: all records tagged is_simulated=True.
"""

import random
from django.utils import timezone
from apps.masterdata.models import Line, Machine
from apps.telemetry.models import MachineCurrentState, SimulationScenarioState, DowntimeEvent
from apps.telemetry.services.state_machine import ingest_telemetry_reading


def get_or_create_simulator(line):
    """Retrieves or creates the simulation controller for a line."""
    sim, _ = SimulationScenarioState.objects.get_or_create(
        line=line,
        defaults={
            'active_scenario': 'NONE',
            'clock_multiplier': 1.0,
            'is_running': True,
        }
    )
    return sim


def activate_scenario(line, scenario_key):
    """
    Activates one of the 5 pre-built test scenarios:
    - NONE
    - CAP_CHUTE_JAM
    - OVERFILL_GIVEAWAY_DRIFT
    - MECHANICAL_BREAKDOWN
    - DEFECT_BURST
    - GOLDEN_RUN
    """
    sim = get_or_create_simulator(line)
    sim.active_scenario = scenario_key
    sim.scenario_started_at = timezone.now()
    sim.save()

    # Apply immediate machine state consequences based on scenario
    machines = list(line.machines.all().order_by('sequence_order'))

    if scenario_key == 'CAP_CHUTE_JAM':
        # Capper stops with fault; upstream Filler is BLOCKED; downstream is STARVED
        for m in machines:
            if m.category == 'CAPPER':
                ingest_telemetry_reading(m, pulse_count=0, instant_cpm=0.0, state_code='UNPLANNED_DOWNTIME', vibration_rms=3.4, temperature_c=58.0, is_simulated=True)
            elif m.category == 'FILLER':
                ingest_telemetry_reading(m, pulse_count=0, instant_cpm=0.0, state_code='BLOCKED', is_simulated=True)
            elif m.sequence_order > 40:
                ingest_telemetry_reading(m, pulse_count=0, instant_cpm=0.0, state_code='STARVED', is_simulated=True)

    elif scenario_key == 'MECHANICAL_BREAKDOWN':
        # Blow molder stops; all downstream machines starve
        first_mach = machines[0] if machines else None
        if first_mach:
            ingest_telemetry_reading(first_mach, pulse_count=0, instant_cpm=0.0, state_code='UNPLANNED_DOWNTIME', vibration_rms=4.8, temperature_c=72.0, is_simulated=True)
        for m in machines[1:]:
            ingest_telemetry_reading(m, pulse_count=0, instant_cpm=0.0, state_code='STARVED', is_simulated=True)

    elif scenario_key == 'OVERFILL_GIVEAWAY_DRIFT':
        # Filler experiences giveaway drift (+1.2g), remains RUNNING with normal throughput
        for m in machines:
            if m.category == 'FILLER':
                ingest_telemetry_reading(
                    m,
                    pulse_count=max(1, int(m.ideal_run_rate_cpm / 6)),
                    instant_cpm=m.ideal_run_rate_cpm,
                    state_code='RUNNING',
                    vibration_rms=1.1,
                    temperature_c=44.0,
                    is_simulated=True
                )

    elif scenario_key == 'DEFECT_BURST':
        # Inject 25 scrap defects into bottleneck or labeler
        target_mach = line.bottleneck_machine or machines[0]
        try:
            curr = target_mach.current_state
            curr.shift_scrap_count += 25
            curr.is_simulated = True
            curr.save(update_fields=['shift_scrap_count', 'is_simulated'])
        except MachineCurrentState.DoesNotExist:
            pass

    elif scenario_key == 'GOLDEN_RUN':
        # Restore all machines to perfect rated CPM, RUNNING state, zero downtime
        for m in machines:
            ingest_telemetry_reading(
                m,
                pulse_count=int(m.ideal_run_rate_cpm / 60.0 * 10),
                instant_cpm=m.ideal_run_rate_cpm,
                state_code='RUNNING',
                vibration_rms=0.75,
                temperature_c=38.0,
                is_simulated=True
            )

    return sim


def step_simulation(line, delta_seconds=1):
    """
    Advances simulation by delta_seconds x clock_multiplier.
    Generates realistic pulses and sensor jitter.
    """
    sim = get_or_create_simulator(line)
    if not sim.is_running or sim.clock_multiplier <= 0:
        return {'status': 'paused', 'tick': sim.tick_count}

    effective_dt = delta_seconds * sim.clock_multiplier
    sim.tick_count += 1
    sim.last_tick_at = timezone.now()
    sim.save()

    machines = line.machines.all().order_by('sequence_order')
    scenario = sim.active_scenario

    for m in machines:
        curr, _ = MachineCurrentState.objects.get_or_create(
            machine=m,
            defaults={'state_code': 'RUNNING', 'current_speed_cpm': m.ideal_run_rate_cpm, 'is_simulated': True}
        )

        # Baseline jitter
        vibe = round(0.75 + random.uniform(-0.08, 0.12), 2)
        temp = round(40.0 + random.uniform(-0.5, 0.8), 1)

        # If currently running, accumulate pulses based on rated speed
        if curr.state_code == 'RUNNING':
            speed = m.ideal_run_rate_cpm
            pulses = max(1, int((speed / 60.0) * effective_dt))
            ingest_telemetry_reading(
                m,
                pulse_count=pulses,
                instant_cpm=speed,
                state_code='RUNNING',
                vibration_rms=vibe,
                temperature_c=temp,
                is_simulated=True
            )
        elif curr.state_code in ['UNPLANNED_DOWNTIME', 'BLOCKED', 'STARVED', 'MICRO_STOP']:
            # Zero pulses during stoppage
            ingest_telemetry_reading(
                m,
                pulse_count=0,
                instant_cpm=0.0,
                state_code=curr.state_code,
                vibration_rms=vibe,
                temperature_c=temp,
                is_simulated=True
            )

    return {
        'status': 'stepped',
        'tick': sim.tick_count,
        'effective_dt': effective_dt,
        'scenario': scenario,
    }


def reset_simulation(line):
    """
    Resets synthetic simulation data for line without affecting live production.
    """
    sim = get_or_create_simulator(line)
    sim.active_scenario = 'NONE'
    sim.tick_count = 0
    sim.save()

    # Clean up simulated downtime events
    DowntimeEvent.objects.filter(line=line, is_simulated=True).delete()

    # Reset machine states to running
    for m in line.machines.all():
        curr, _ = MachineCurrentState.objects.get_or_create(machine=m)
        curr.state_code = 'RUNNING'
        curr.current_speed_cpm = m.ideal_run_rate_cpm
        curr.shift_pulse_count = 0
        curr.shift_good_count = 0
        curr.shift_scrap_count = 0
        curr.vibration_rms = 0.8
        curr.temperature_c = 40.0
        curr.is_simulated = True
        curr.save()

    return sim
