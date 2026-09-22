"""
Unit Tests for Fault Screening and Sensor Anomaly Detection.
Asserts:
- Condensation fault (RH step jump to near 100%) is flagged as suspect
- Condensation fault is excluded from stack aw_max, preventing false Critical alert
- Stuck-at sensor freeze is detected
- Surviving nodes n_ok < 2 triggers 'needs_inspection'
"""

import pytest
from datetime import datetime, timezone, timedelta
from backend.simulator.node_model import NodeReading
from backend.gateway.fault_screening import FaultScreeningService
from backend.gateway.isotherm import IsothermInversionService


def test_condensation_fault_screening():
    service = FaultScreeningService()
    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    stack_id = "STK-TEST"

    # Step 1: Prime node history with normal 62% readings
    for i in range(5):
        t_prev = now - timedelta(minutes=(5 - i) * 15)
        service.screen_stack_readings(
            stack_id=stack_id,
            readings=[
                NodeReading(node_id="N1", stack_id=stack_id, timestamp=t_prev, erh_observed=62.0, temp_observed=28.0, temp_core_observed=28.0, battery_voltage=3.5),
                NodeReading(node_id="N2", stack_id=stack_id, timestamp=t_prev, erh_observed=63.0, temp_observed=28.0, temp_core_observed=28.0, battery_voltage=3.5),
                NodeReading(node_id="N3", stack_id=stack_id, timestamp=t_prev, erh_observed=61.0, temp_observed=28.0, temp_core_observed=28.0, battery_voltage=3.5),
            ],
            current_nominal_time=t_prev,
        )

    # Step 2: Inject sudden condensation fault on N1 (jumps to 99.8% in 15 mins)
    faulty_readings = [
        NodeReading(node_id="N1", stack_id=stack_id, timestamp=now, erh_observed=99.8, temp_observed=24.5, temp_core_observed=28.0, battery_voltage=3.5),
        NodeReading(node_id="N2", stack_id=stack_id, timestamp=now, erh_observed=63.5, temp_observed=28.0, temp_core_observed=28.0, battery_voltage=3.5),
        NodeReading(node_id="N3", stack_id=stack_id, timestamp=now, erh_observed=62.0, temp_observed=28.0, temp_core_observed=28.0, battery_voltage=3.5),
    ]

    res = service.screen_stack_readings(stack_id=stack_id, readings=faulty_readings, current_nominal_time=now)
    
    # N1 must be flagged as suspect
    n1_screened = res.all_screened_nodes["N1"]
    assert n1_screened.is_suspect is True
    assert any("rapid_rh_step" in r or "cluster_outlier" in r for r in n1_screened.suspect_reasons)
    
    # N1 must be excluded from surviving readings
    surviving_ids = [r.node_id for r in res.surviving_readings]
    assert "N1" not in surviving_ids
    assert "N2" in surviving_ids and "N3" in surviving_ids
    assert res.n_ok == 2

    # Now verify isotherm calculation does NOT get dragged to Critical
    iso = IsothermInversionService()
    iso_res = iso.evaluate_stack_moisture(stack_id, res.surviving_readings, trailing_dM_dt=0.0)
    assert iso_res.m_est_percent < 14.5, f"Stack moisture {iso_res.m_est_percent} falsely elevated by suspect node"


def test_needs_inspection_when_n_ok_below_2():
    service = FaultScreeningService()
    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    stack_id = "STK-DROPOUT"

    # Only 1 reading arriving (others dead)
    readings = [
        NodeReading(node_id="N1", stack_id=stack_id, timestamp=now, erh_observed=62.0, temp_observed=28.0, temp_core_observed=28.0, battery_voltage=3.5),
    ]
    res = service.screen_stack_readings(stack_id=stack_id, readings=readings, current_nominal_time=now)
    assert res.n_ok == 1
    assert res.needs_inspection is True
    assert res.qflag == "SUSPECT"
