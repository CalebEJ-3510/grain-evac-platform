"""
Unit Tests for Dispatch Optimizer and Localized Reason Generation.
Asserts:
- Greedy knapsack capacity bound
- Precedence-aware DAG 2-opt resolution of blocked aisle dependencies
- Programmatic bilingual reason string generation in English and Tamil
"""

import pytest
from datetime import datetime, timezone
from backend.engine.dispatch import DispatchOptimizer
from backend.engine.epi import EPIScore
from backend.engine.sub_indices import SubIndexVector
from backend.engine.weights_store import SubIndexWeights
from backend.gateway.state_record import FusedStateRecord


def make_test_item(sid: str, mass: float, epi: float, dm_dt: float = 0.0) -> tuple[FusedStateRecord, EPIScore]:
    rec = FusedStateRecord(
        stack_id=sid,
        ts=datetime.now(timezone.utc),
        aw_max=0.65,
        m_est=15.0,
        dm_dt_24h=dm_dt,
        t_core=29.0,
        t_amb_ma24=28.0,
        mra=1.0,
        r72=35.0,
        p_rain=0.75,
        rhf=78.0,
        mass_t=mass,
        age_d=30.0,
        n_ok=4,
        qflag="OK",
        active_branch="adsorption",
        vulnerability_score=0.4,
        needs_inspection=False,
        governing_node_id=f"{sid}-N1",
    )
    score = EPIScore(
        stack_id=sid,
        timestamp=rec.ts,
        raw_epi=epi,
        final_epi=epi,
        override_fired=False,
        band="Priority" if epi >= 50 else "Watch",
        sub_indices=SubIndexVector(s_M=0.33, s_R=0.2, s_T=0.1, s_A=0.15, s_F=0.4, s_V=0.4),
        active_weights=SubIndexWeights(),
        config_version_id=1,
    )
    return rec, score


def test_greedy_capacity_constraint():
    opt = DispatchOptimizer()
    now = datetime.now(timezone.utc)
    
    # 3 stacks of 48 MT each = 144 MT. Capacity is 120 MT.
    r1, s1 = make_test_item("STK-01", 48.0, 85.0)
    r2, s2 = make_test_item("STK-02", 48.0, 70.0)
    r3, s3 = make_test_item("STK-03", 48.0, 55.0)

    records = {"STK-01": r1, "STK-02": r2, "STK-03": r3}
    scores = {"STK-01": s1, "STK-02": s2, "STK-03": s3}

    plan = opt.optimize_dispatch(
        current_time=now,
        records=records,
        epi_scores=scores,
        truck_capacity_mt=120.0,
    )

    # 48 + 48 = 96 <= 120. 3rd stack (48) would make 144 > 120, so only 2 stacks should be queued
    assert plan.total_loaded_mt <= 120.0
    assert len(plan.queue) == 2
    assert plan.queue[0].stack_id == "STK-01"
    assert plan.queue[1].stack_id == "STK-02"


def test_precedence_dag_resolution():
    """Verify that an urgent inner stack causes its blocking outer stack to be loaded first."""
    opt = DispatchOptimizer()
    now = datetime.now(timezone.utc)

    # STK-BACK (inner row) has Critical EPI (92) but is blocked by STK-FRONT (EPI 45)
    r_back, s_back = make_test_item("STK-BACK", 48.0, 92.0)
    r_front, s_front = make_test_item("STK-FRONT", 48.0, 45.0)
    r_other, s_other = make_test_item("STK-OTHER", 48.0, 60.0)

    records = {"STK-BACK": r_back, "STK-FRONT": r_front, "STK-OTHER": r_other}
    scores = {"STK-BACK": s_back, "STK-FRONT": s_front, "STK-OTHER": s_other}
    precedence = {"STK-BACK": "STK-FRONT"}  # STK-BACK is blocked by STK-FRONT

    plan = opt.optimize_dispatch(
        current_time=now,
        records=records,
        epi_scores=scores,
        truck_capacity_mt=120.0,
        precedence_dag=precedence,
    )

    # In feasible schedule, STK-FRONT must be loaded BEFORE STK-BACK
    queue_ids = [q.stack_id for q in plan.queue]
    assert "STK-FRONT" in queue_ids
    assert "STK-BACK" in queue_ids
    assert queue_ids.index("STK-FRONT") < queue_ids.index("STK-BACK"), "Blocking stack must precede blocked stack"
    assert plan.optimization_improvement_gain >= 0.0


def test_bilingual_reason_strings():
    opt = DispatchOptimizer()
    r, s = make_test_item("STK-01", 48.0, 75.0, dm_dt=0.35)
    
    en_reason, ta_reason = opt.generate_reasons(r, s)
    assert len(en_reason) > 5
    assert len(ta_reason) > 5
    # Confirm Tamil characters present in Tamil reason
    has_tamil_char = any('\u0B80' <= ch <= '\u0BFF' for ch in ta_reason)
    assert has_tamil_char, f"Tamil reason must contain Tamil unicode characters: {ta_reason}"
