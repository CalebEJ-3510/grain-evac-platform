"""
Module 2: Sorption Isotherm Inversion (Modified Chung-Pfost).
Inverts equilibrium relative humidity and grain temperature to estimate grain moisture (%wb).
Strictly implements the worst-case (aw_max) pooling rule across surviving nodes
and dynamically selects the hysteresis branch based on trailing dM/dt sign.
"""

from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel
from backend.gateway.fault_screening import ScreenedReading

# Default Rough Rice Constants (ASABE D245.7)
DEFAULT_ISOTHERM_PARAMS = {
    "adsorption": {"A": 502.8, "B": 16.5, "C": 41.5},
    "desorption": {"A": 591.4, "B": 16.8, "C": 35.7},
}


class IsothermResult(BaseModel):
    stack_id: str
    aw_max: float
    m_est_percent: float
    governing_node_id: str
    active_branch: str  # "adsorption" or "desorption"
    t_core_at_worst_case: float
    t_core_stack_max: float


class IsothermInversionService:
    def __init__(self, params: Optional[Dict[str, Dict[str, float]]] = None):
        self.params = params or DEFAULT_ISOTHERM_PARAMS

    def invert_node_reading(
        self,
        aw: float,
        temp_c: float,
        branch: str = "adsorption",
    ) -> float:
        """
        Computes moisture content (%wb) from water activity aw (0 to 1) and temperature (°C).
        M = -(1 / B) * ln[ -(T + C) * ln(RH) / A ]
        """
        aw = max(0.01, min(0.999, aw))
        p = self.params.get(branch, self.params["adsorption"])
        A, B, C = p["A"], p["B"], p["C"]
        
        # ln(aw) is negative for aw < 1
        inner = - (temp_c + C) * math.log(aw) / A
        if inner <= 0:
            inner = 1e-6
            
        m_db = - (1.0 / B) * math.log(inner)
        # Convert dry basis decimal to wet basis percentage: M_wb = M_db / (1 + M_db) * 100
        m_wb = m_db / (1.0 + m_db)
        return max(1.0, min(35.0, m_wb * 100.0))

    def evaluate_stack_moisture(
        self,
        stack_id: str,
        surviving_readings: List[ScreenedReading],
        trailing_dM_dt: float = 0.0,
    ) -> IsothermResult:
        """
        Computes M_est for a stack.
        Per §6.2: Spoilage is local; uses the worst-case (aw_max) reading across surviving nodes,
        NOT the spatial mean.
        Branch selection: if trailing dM/dt >= 0 -> adsorption (re-wetting), else desorption (drying).
        """
        if not surviving_readings:
            # Fallback if all nodes are dead/suspect
            return IsothermResult(
                stack_id=stack_id,
                aw_max=0.60,
                m_est_percent=13.5,
                governing_node_id="NONE",
                active_branch="adsorption",
                t_core_at_worst_case=28.0,
                t_core_stack_max=28.0,
            )
            
        branch = "adsorption" if trailing_dM_dt >= 0.0 else "desorption"
        
        # Find governing worst-case node (highest water activity)
        worst_node = max(surviving_readings, key=lambda r: r.water_activity)
        max_core_temp = max(r.temp_core_c for r in surviving_readings)
        
        # Invert at worst-case aw and corresponding node core temperature
        m_est = self.invert_node_reading(
            aw=worst_node.water_activity,
            temp_c=worst_node.temp_core_c,
            branch=branch,
        )
        
        return IsothermResult(
            stack_id=stack_id,
            aw_max=round(worst_node.water_activity, 4),
            m_est_percent=round(m_est, 2),
            governing_node_id=worst_node.node_id,
            active_branch=branch,
            t_core_at_worst_case=round(worst_node.temp_core_c, 2),
            t_core_stack_max=round(max_core_temp, 2),
        )
