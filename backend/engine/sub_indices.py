"""
Module 3: Sub-Index Computation Engine.
Computes the 6 physical sub-indices (s_M, s_R, s_T, s_A, s_F, s_V)
strictly clamped to [0, 1] using configurable anchors.
"""

from __future__ import annotations
from typing import Dict
from pydantic import BaseModel
from backend.gateway.state_record import FusedStateRecord
from backend.engine.weights_store import AnchorsConfig


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


class SubIndexVector(BaseModel):
    s_M: float  # Moisture state (0-1)
    s_R: float  # Rate of change (0-1)
    s_T: float  # Thermal anomaly (0-1)
    s_A: float  # Accumulated mould risk (0-1)
    s_F: float  # Weather forecast risk (0-1)
    s_V: float  # Vulnerability rubric (0-1)

    def as_dict(self) -> Dict[str, float]:
        return {
            "s_M": self.s_M,
            "s_R": self.s_R,
            "s_T": self.s_T,
            "s_A": self.s_A,
            "s_F": self.s_F,
            "s_V": self.s_V,
        }


class SubIndexCalculator:
    def __init__(self, anchors: AnchorsConfig):
        self.anchors = anchors

    def compute(self, record: FusedStateRecord) -> SubIndexVector:
        """
        Computes all 6 clamped sub-indices from a FusedStateRecord.
        """
        # 1. Moisture State (s_M): clamp01((M_est - 14.0) / (17.0 - 14.0))
        m_span = max(0.1, self.anchors.m_crit - self.anchors.m_safe)
        s_M = clamp01((record.m_est - self.anchors.m_safe) / m_span)

        # 2. Rate of Change (s_R): clamp01(dM_dt_24h / 0.5)
        s_R = clamp01(record.dm_dt_24h / max(0.01, self.anchors.dm_dt_scale))

        # 3. Thermal Anomaly (s_T): clamp01((T_core - T_amb_ma24 - 2) / (8 - 2))
        t_diff = record.t_core - record.t_amb_ma24
        t_span = max(0.1, self.anchors.t_diff_max - self.anchors.t_diff_min)
        s_T = clamp01((t_diff - self.anchors.t_diff_min) / t_span)

        # 4. Accumulated Mould Risk (s_A): clamp01(MRA / 6.0)
        s_A = clamp01(record.mra / max(0.1, self.anchors.mra_scale))

        # 5. Weather Forecast Risk (s_F): clamp01(0.7 * p_rain * (R72/50) + 0.3 * (RHf - 70)/25)
        r72_term = record.p_rain * (record.r72 / max(1.0, self.anchors.r72_scale))
        rh_term = (record.rhf - self.anchors.rhf_offset) / max(1.0, self.anchors.rhf_span)
        s_F = clamp01(0.7 * r72_term + 0.3 * rh_term)

        # 6. Static Vulnerability Rubric (s_V): score / 10
        s_V = clamp01(record.vulnerability_score)

        return SubIndexVector(
            s_M=round(s_M, 4),
            s_R=round(s_R, 4),
            s_T=round(s_T, 4),
            s_A=round(s_A, 4),
            s_F=round(s_F, 4),
            s_V=round(s_V, 4),
        )
