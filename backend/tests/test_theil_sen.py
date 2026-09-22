"""
Unit Tests for Theil-Sen Robust Regression vs OLS.
Asserts that single-epoch transient outliers (such as from condensation)
do not corrupt the estimated moisture rate of change dM/dt.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from backend.gateway.state_record import StateReconstructionService


def test_theil_sen_outlier_resistance():
    service = StateReconstructionService()
    base_time = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    stack_id = "TEST-STK-01"

    # Generate 24 hours of stable data with a true slope of +0.2 %wb/day
    true_slope_per_day = 0.20
    for step in range(96):
        t = base_time + timedelta(minutes=step * 15)
        day_frac = (step * 15) / 1440.0
        m = 13.5 + true_slope_per_day * day_frac
        
        # Inject transient condensation spikes at step 50 and 51 (+4.0% surge)
        if step in [50, 51]:
            m += 4.0
            
        slope = service.compute_theil_sen_slope(stack_id, t, m)

    # The recovered Theil-Sen slope should remain close to the true 0.20 %wb/day
    assert abs(slope - true_slope_per_day) < 0.08, f"Theil-Sen slope {slope} was corrupted by outliers (expected ~{true_slope_per_day})"
