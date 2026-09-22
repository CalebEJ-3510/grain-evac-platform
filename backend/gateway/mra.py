"""
Module 2: Mould Risk Accumulator (MRA).
Implements the 14-day trailing exposure integral of fungal metabolic rate:
MRA(t) = ∫[t-τ, t] max(0, a_w(u) - 0.65) · Q10^((T(u) - 25) / 10) du

Exact benchmark verification:
- 24h at a_w = 0.75, 25°C -> 2.4 a_w·h
- 24h at a_w = 0.75, 35°C -> 4.8 a_w·h
"""

from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional


class MouldRiskAccumulator:
    def __init__(
        self,
        tau_days: float = 14.0,
        fungal_threshold_aw: float = 0.65,
        q10: float = 2.0,
        mra_crit: float = 6.0,
    ):
        self.tau_days = tau_days
        self.fungal_threshold = fungal_threshold_aw
        self.q10 = q10
        self.mra_crit = mra_crit
        
        # History per stack: stack_id -> list of (timestamp, aw_max, temp_core_c)
        self.stack_history: Dict[str, List[Tuple[datetime, float, float]]] = {}

    @staticmethod
    def instantaneous_mould_rate(
        aw: float,
        temp_c: float,
        threshold: float = 0.65,
        q10: float = 2.0,
    ) -> float:
        """
        Computes the integrand: max(0, a_w - 0.65) * Q10^((T - 25) / 10).
        Units: a_w (effective biological activity rate).
        """
        excess_aw = max(0.0, aw - threshold)
        if excess_aw <= 0.0:
            return 0.0
        temp_factor = math.pow(q10, (temp_c - 25.0) / 10.0)
        return excess_aw * temp_factor

    def add_epoch_and_integrate(
        self,
        stack_id: str,
        timestamp: datetime,
        aw_max: float,
        temp_core_c: float,
    ) -> float:
        """
        Appends epoch reading and numerically integrates MRA over trailing tau window using trapezoidal rule.
        Returns: MRA in a_w·hours.
        """
        history = self.stack_history.setdefault(stack_id, [])
        history.append((timestamp, aw_max, temp_core_c))
        
        # Prune points older than tau_days
        cutoff = timestamp - timedelta(days=self.tau_days)
        history = [p for p in history if p[0] >= cutoff]
        self.stack_history[stack_id] = history
        
        if len(history) < 2:
            return 0.0
            
        total_mra = 0.0
        for i in range(1, len(history)):
            t0, aw0, temp0 = history[i - 1]
            t1, aw1, temp1 = history[i]
            
            dt_hours = (t1 - t0).total_seconds() / 3600.0
            # Safety limit: if gap is huge (e.g. initial seed), cap dt to 0.5h
            dt_hours = min(0.5, max(0.0, dt_hours))
            
            rate0 = self.instantaneous_mould_rate(aw0, temp0, self.fungal_threshold, self.q10)
            rate1 = self.instantaneous_mould_rate(aw1, temp1, self.fungal_threshold, self.q10)
            
            # Trapezoidal numerical integration
            total_mra += 0.5 * (rate0 + rate1) * dt_hours
            
        return round(total_mra, 3)

    def calculate_discrete_window(
        self,
        samples: List[Tuple[datetime, float, float]],
    ) -> float:
        """Helper for test verification over synthetic sample sequences."""
        if len(samples) < 2:
            return 0.0
        total_mra = 0.0
        for i in range(1, len(samples)):
            t0, aw0, temp0 = samples[i - 1]
            t1, aw1, temp1 = samples[i]
            dt_hours = (t1 - t0).total_seconds() / 3600.0
            rate0 = self.instantaneous_mould_rate(aw0, temp0, self.fungal_threshold, self.q10)
            rate1 = self.instantaneous_mould_rate(aw1, temp1, self.fungal_threshold, self.q10)
            total_mra += 0.5 * (rate0 + rate1) * dt_hours
        return round(total_mra, 3)
