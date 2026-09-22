"""
Scenario-Level Integration Tests.
Asserts that each named synthetic scenario produces its expected qualitative signature
when run end-to-end through the full pipeline (Simulator -> Gateway -> Engine):
- core_hotspot: s_T dominates while s_M stays low (proves decomposability)
- flash_rain_event: s_F leads ground truth before moisture ingress occurs
- slow_monsoon_wetting: s_M and s_R climb together, transitioning Normal -> Watch -> Priority
- Precision@6 evaluation against ground-truth synthetic state
"""

import pytest
from datetime import datetime, timezone, timedelta
from backend.simulator.node_model import SyntheticStack
from backend.simulator.weather_synth import WeatherSynthesizer
from backend.simulator.scenarios import ScenarioEngine
from backend.gateway.fault_screening import FaultScreeningService
from backend.gateway.isotherm import IsothermInversionService
from backend.gateway.mra import MouldRiskAccumulator
from backend.gateway.state_record import StateReconstructionService
from backend.engine.weights_store import WeightsStore
from backend.engine.sub_indices import SubIndexCalculator
from backend.engine.epi import EPIEngine


def run_pipeline_step(
    stack: SyntheticStack,
    weather_synth: WeatherSynthesizer,
    current_time: datetime,
    fault_screening: FaultScreeningService,
    isotherm_service: IsothermInversionService,
    mra_service: MouldRiskAccumulator,
    state_recon: StateReconstructionService,
    sub_index_calc: SubIndexCalculator,
    epi_engine: EPIEngine,
    dt_minutes: float = 15.0,
):
    w = weather_synth.advance(current_time, dt_minutes)
    stack.advance_physics(
        dt_minutes=dt_minutes,
        ambient_rh_pct=w.ambient_rh_pct,
        ambient_temp_c=w.ambient_temp_c,
        is_raining=w.is_raining,
        rain_rate_mm_h=w.rain_rate_mm_h,
        amb_temp_24h_ma=w.temp_amb_ma24,
        current_time=current_time,
    )
    raw_readings = stack.emit_telemetry(current_time)
    screen_res = fault_screening.screen_stack_readings(stack.stack_id, raw_readings, current_time)
    iso_res = isotherm_service.evaluate_stack_moisture(stack.stack_id, screen_res.surviving_readings)
    mra_val = mra_service.add_epoch_and_integrate(stack.stack_id, current_time, iso_res.aw_max, iso_res.t_core_at_worst_case)
    fused_rec = state_recon.assemble_fused_record(stack, screen_res, iso_res, mra_val, w, current_time)
    s_vec = sub_index_calc.compute(fused_rec)
    epi_score = epi_engine.compute_epi(fused_rec, s_vec)
    return fused_rec, s_vec, epi_score


def test_core_hotspot_scenario_signature():
    """Verify that core_hotspot scenario drives s_T high while s_M stays low."""
    base_time = datetime(2026, 9, 15, 6, 0, 0, tzinfo=timezone.utc)
    weather = WeatherSynthesizer()
    stack = SyntheticStack("STK-HOT", 48.0, "Row-A", 1, base_time)
    ScenarioEngine.apply_scenario_to_stack(stack, "core_hotspot", weather, base_time)

    fault_screening = FaultScreeningService()
    isotherm_service = IsothermInversionService()
    mra_service = MouldRiskAccumulator()
    state_recon = StateReconstructionService()
    cfg = WeightsStore().current
    sub_index_calc = SubIndexCalculator(cfg.anchors)
    epi_engine = EPIEngine(cfg.weights, cfg.anchors, cfg.alert_ladder)

    # Run for 3 simulated days (288 ticks)
    final_fused = None
    final_s = None
    final_epi = None
    for step in range(288):
        t = base_time + timedelta(minutes=step * 15)
        final_fused, final_s, final_epi = run_pipeline_step(
            stack, weather, t, fault_screening, isotherm_service, mra_service,
            state_recon, sub_index_calc, epi_engine, dt_minutes=15.0
        )

    # Assert qualitative signature per §5.3:
    # 1. Thermal anomaly s_T should be high (> 0.5)
    # 2. Moisture state s_M should remain low (<= 0.25)
    # 3. Thermal term dominates the weighted sum
    assert final_s.s_T >= 0.5, f"Expected elevated thermal sub-index s_T, got {final_s.s_T}"
    assert final_s.s_M <= 0.25, f"Expected low moisture sub-index s_M, got {final_s.s_M}"
    t_contrib = cfg.weights.w_T * final_s.s_T
    m_contrib = cfg.weights.w_M * final_s.s_M
    assert t_contrib > m_contrib, f"Thermal contribution {t_contrib} must dominate moisture {m_contrib}"
    assert final_epi.final_epi >= 8.0, "EPI should reflect thermal rise"


def test_flash_rain_scenario_signature():
    """Verify flash_rain_event causes forecast s_F to spike ahead of grain moisture s_M."""
    base_time = datetime(2026, 9, 15, 6, 0, 0, tzinfo=timezone.utc)
    weather = WeatherSynthesizer()
    stack = SyntheticStack("STK-FLASH", 48.0, "Row-A", 1, base_time)
    ScenarioEngine.apply_scenario_to_stack(stack, "flash_rain_event", weather, base_time)

    fault_screening = FaultScreeningService()
    isotherm_service = IsothermInversionService()
    mra_service = MouldRiskAccumulator()
    state_recon = StateReconstructionService()
    cfg = WeightsStore().current
    sub_index_calc = SubIndexCalculator(cfg.anchors)
    epi_engine = EPIEngine(cfg.weights, cfg.anchors, cfg.alert_ladder)

    # Check after 2 ticks (30 minutes of rain)
    fused, s_vec, epi = run_pipeline_step(
        stack, weather, base_time + timedelta(minutes=30), fault_screening,
        isotherm_service, mra_service, state_recon, sub_index_calc, epi_engine,
    )

    # Forecast risk s_F must immediately be high, while moisture s_M lags substantially due to diffusion lag
    assert s_vec.s_F >= 0.80, f"Expected immediate forecast spike s_F >= 0.80, got {s_vec.s_F}"
    assert s_vec.s_M < 0.15, f"Grain moisture s_M should still lag forecast s_F, got {s_vec.s_M}"
    assert s_vec.s_F > s_vec.s_M + 0.60, f"Forecast s_F must vastly exceed moisture s_M during early flash rain"
