"""
Unit Tests for Modified Chung-Pfost Isotherm Inversion and Forward Physics.
Asserts:
- Round-trip fidelity between forward and inverse models for both branches
- Physical plausibility across moisture (11% to 22%) and temperature (18°C to 40°C)
- Worst-case (aw_max) pooling vs mean pooling
"""

import pytest
import numpy as np
from backend.simulator.node_model import forward_chung_pfost, inverse_chung_pfost
from backend.gateway.isotherm import IsothermInversionService
from backend.gateway.fault_screening import ScreenedReading
from datetime import datetime, timezone


def test_isotherm_round_trip_adsorption():
    """Verify forward -> inverse reproduces original moisture within 0.05%wb on adsorption branch."""
    service = IsothermInversionService()
    test_moistures = [11.0, 12.5, 14.0, 15.5, 17.0, 19.0]
    test_temps = [20.0, 25.0, 30.0, 35.0]

    for m_true in test_moistures:
        for t_true in test_temps:
            # 1. Forward model: Moisture & Temp -> ERH/aw
            aw = forward_chung_pfost(m_true, t_true, branch="adsorption")
            assert 0.01 <= aw <= 0.99, f"aw {aw} out of plausible physical range"
            
            # 2. Gateway inversion: aw & Temp -> Estimated Moisture
            m_recovered = service.invert_node_reading(aw, t_true, branch="adsorption")
            
            diff = abs(m_true - m_recovered)
            assert diff < 0.05, f"Round-trip failed at M={m_true}, T={t_true}: recovered {m_recovered} (diff={diff})"


def test_isotherm_round_trip_desorption():
    """Verify forward -> inverse reproduces original moisture within 0.05%wb on desorption branch."""
    service = IsothermInversionService()
    test_moistures = [11.5, 13.0, 14.5, 16.0, 18.0]
    test_temps = [22.0, 28.0, 34.0]

    for m_true in test_moistures:
        for t_true in test_temps:
            aw = forward_chung_pfost(m_true, t_true, branch="desorption")
            m_recovered = service.invert_node_reading(aw, t_true, branch="desorption")
            diff = abs(m_true - m_recovered)
            assert diff < 0.05, f"Desorption round-trip failed at M={m_true}, T={t_true}: diff={diff}"


def test_hysteresis_offset_visible():
    """At identical aw and temp, desorption moisture is higher than adsorption moisture by ~0.5-1.5 %wb."""
    service = IsothermInversionService()
    aw = 0.70
    temp = 28.0
    
    m_ads = service.invert_node_reading(aw, temp, branch="adsorption")
    m_des = service.invert_node_reading(aw, temp, branch="desorption")
    
    hysteresis_diff = m_des - m_ads
    assert 0.4 <= hysteresis_diff <= 1.8, f"Hysteresis difference {hysteresis_diff} not in 0.4 - 1.8 %wb range"


def test_worst_case_aw_max_pooling():
    """Verify stack moisture evaluates at the worst-case (aw_max) node rather than spatial mean."""
    service = IsothermInversionService()
    now = datetime.now(timezone.utc)
    
    # Simulate 3 nodes: 2 dry interior nodes, 1 wet perimeter node
    r1 = ScreenedReading(
        node_id="N1", stack_id="STK-01", aligned_timestamp=now, raw_timestamp=now,
        erh=58.0, water_activity=0.58, temp_c=28.0, temp_core_c=28.0, battery_voltage=3.5,
    )
    r2 = ScreenedReading(
        node_id="N2", stack_id="STK-01", aligned_timestamp=now, raw_timestamp=now,
        erh=60.0, water_activity=0.60, temp_c=28.0, temp_core_c=28.0, battery_voltage=3.5,
    )
    r3_wet = ScreenedReading(
        node_id="N3", stack_id="STK-01", aligned_timestamp=now, raw_timestamp=now,
        erh=86.0, water_activity=0.86, temp_c=28.0, temp_core_c=28.0, battery_voltage=3.5,
    )

    res = service.evaluate_stack_moisture(
        stack_id="STK-01",
        surviving_readings=[r1, r2, r3_wet],
        trailing_dM_dt=0.2,
    )
    
    assert res.governing_node_id == "N3"
    assert res.aw_max == 0.86
    # Moisture at aw=0.86 should be ~17% or higher
    assert res.m_est_percent >= 16.5
