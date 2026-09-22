"""
Unit Tests for Sub-Indices, EPI Engine, and Safety Override Rules.
Asserts:
- Clamping of all sub-indices to [0, 1]
- Hard safety override fires when M_est >= 17.0% or MRA >= 6.0 a_w·h
- Correct band categorization
"""

import pytest
from datetime import datetime, timezone
from backend.engine.sub_indices import SubIndexCalculator, clamp01
from backend.engine.epi import EPIEngine
from backend.engine.weights_store import WeightsStore, SubIndexWeights, AnchorsConfig, AlertLadderConfig
from backend.gateway.state_record import FusedStateRecord


def make_mock_record(m_est: float = 13.5, dm_dt: float = 0.0, t_core: float = 28.0, t_amb: float = 28.0, mra: float = 0.0, r72: float = 0.0, p_rain: float = 0.0, rhf: float = 65.0, vuln: float = 0.2) -> FusedStateRecord:
    return FusedStateRecord(
        stack_id="TEST-01",
        ts=datetime.now(timezone.utc),
        aw_max=0.60,
        m_est=m_est,
        dm_dt_24h=dm_dt,
        t_core=t_core,
        t_amb_ma24=t_amb,
        mra=mra,
        r72=r72,
        p_rain=p_rain,
        rhf=rhf,
        mass_t=48.0,
        age_d=20.0,
        n_ok=4,
        qflag="OK",
        active_branch="adsorption",
        vulnerability_score=vuln,
        needs_inspection=False,
        governing_node_id="N1",
    )


def test_sub_indices_clamping():
    calc = SubIndexCalculator(AnchorsConfig())
    
    # Sub-zero and excess inputs
    rec_low = make_mock_record(m_est=12.0, dm_dt=-1.0, t_core=20.0, t_amb=30.0, mra=0.0, r72=0.0, p_rain=0.0, rhf=40.0, vuln=0.0)
    s_low = calc.compute(rec_low)
    assert s_low.s_M == 0.0
    assert s_low.s_R == 0.0
    assert s_low.s_T == 0.0
    assert s_low.s_A == 0.0
    assert s_low.s_F == 0.0
    assert s_low.s_V == 0.0

    rec_high = make_mock_record(m_est=20.0, dm_dt=2.5, t_core=42.0, t_amb=25.0, mra=15.0, r72=120.0, p_rain=1.0, rhf=99.0, vuln=1.0)
    s_high = calc.compute(rec_high)
    assert s_high.s_M == 1.0
    assert s_high.s_R == 1.0
    assert s_high.s_T == 1.0
    assert s_high.s_A == 1.0
    assert s_high.s_F == 1.0
    assert s_high.s_V == 1.0


def test_safety_override_rule_moisture():
    """Verify that when M_est >= 17.0%, EPI is clamped to at least 90 regardless of weighted sum."""
    store = WeightsStore()
    cfg = store.current
    engine = EPIEngine(weights=cfg.weights, anchors=cfg.anchors, ladder_config=cfg.alert_ladder)
    calc = SubIndexCalculator(cfg.anchors)

    # Low other indices but moisture breach (17.2%)
    rec = make_mock_record(m_est=17.2, dm_dt=0.0, t_core=28.0, t_amb=28.0, mra=0.0, r72=0.0, p_rain=0.0, rhf=60.0, vuln=0.1)
    s_vec = calc.compute(rec)
    
    # Weighted sum alone: w_M * 1.0 = 0.28 * 100 = 28 + vuln = ~30 (Watch band)
    score = engine.compute_epi(rec, s_vec)
    assert score.raw_epi < 40.0, "Raw weighted sum should be low"
    assert score.override_fired is True
    assert score.final_epi >= 90.0, f"Final EPI {score.final_epi} must be >= 90 when override fires"
    assert score.band == "Critical"


def test_safety_override_rule_mra():
    """Verify that when MRA >= 6.0 a_w·h, EPI is clamped to at least 90."""
    store = WeightsStore()
    cfg = store.current
    engine = EPIEngine(weights=cfg.weights, anchors=cfg.anchors, ladder_config=cfg.alert_ladder)
    calc = SubIndexCalculator(cfg.anchors)

    rec = make_mock_record(m_est=13.8, dm_dt=0.0, t_core=28.0, t_amb=28.0, mra=6.5, r72=0.0, p_rain=0.0, rhf=60.0, vuln=0.0)
    s_vec = calc.compute(rec)
    
    score = engine.compute_epi(rec, s_vec)
    assert score.override_fired is True
    assert score.final_epi >= 90.0
    assert score.band == "Critical"
