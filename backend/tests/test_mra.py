"""
Unit Tests for Mould Risk Accumulator (MRA).
Asserts exact numerical reproduction of the spec's worked examples:
- 24h at aw = 0.75, 25°C -> 2.4 a_w·h
- 24h at aw = 0.75, 35°C -> 4.8 a_w·h
- Zero accumulation below aw = 0.65 threshold
"""

import pytest
from datetime import datetime, timezone, timedelta
from backend.gateway.mra import MouldRiskAccumulator


def test_mra_worked_example_25c():
    """Verify 24h exposure at aw=0.75 and 25°C equals exactly 2.4 a_w·h."""
    mra_engine = MouldRiskAccumulator(tau_days=14.0, fungal_threshold_aw=0.65, q10=2.0)
    base_time = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # Generate 15-minute points for 24 hours (96 intervals)
    samples = []
    for step in range(97):
        t = base_time + timedelta(minutes=step * 15)
        samples.append((t, 0.75, 25.0))

    result = mra_engine.calculate_discrete_window(samples)
    assert abs(result - 2.40) < 0.02, f"Expected 2.4 a_w·h, got {result}"


def test_mra_worked_example_35c():
    """Verify 24h exposure at aw=0.75 and 35°C equals exactly 4.8 a_w·h (Q10 = 2)."""
    mra_engine = MouldRiskAccumulator(tau_days=14.0, fungal_threshold_aw=0.65, q10=2.0)
    base_time = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    samples = []
    for step in range(97):
        t = base_time + timedelta(minutes=step * 15)
        samples.append((t, 0.75, 35.0))

    result = mra_engine.calculate_discrete_window(samples)
    assert abs(result - 4.80) < 0.02, f"Expected 4.8 a_w·h, got {result}"


def test_mra_zero_below_threshold():
    """Verify aw <= 0.65 produces zero accumulation regardless of temperature."""
    mra_engine = MouldRiskAccumulator(tau_days=14.0, fungal_threshold_aw=0.65, q10=2.0)
    base_time = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    samples = []
    for step in range(97):
        t = base_time + timedelta(minutes=step * 15)
        samples.append((t, 0.63, 38.0))  # Dry grain in hot sun

    result = mra_engine.calculate_discrete_window(samples)
    assert result == 0.0, f"Expected 0.0 a_w·h below threshold, got {result}"
