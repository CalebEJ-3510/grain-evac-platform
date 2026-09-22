"""
Module 2: Fused State Record Generation & Persistence.
Calculates trailing 24h Theil-Sen robust regression slope (dM/dt),
normalizes vulnerability rubric, and builds the strict 15-field Fused State Record.
"""

from __future__ import annotations
import numpy as np
from scipy.stats import theilslopes
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from backend.gateway.fault_screening import ScreeningResult
from backend.gateway.isotherm import IsothermResult
from backend.simulator.weather_synth import WeatherState
from backend.simulator.node_model import SyntheticStack


class FusedStateRecord(BaseModel):
    stack_id: str
    ts: datetime
    aw_max: float
    m_est: float
    dm_dt_24h: float
    t_core: float
    t_amb_ma24: float
    mra: float
    r72: float
    p_rain: float
    rhf: float
    mass_t: float
    age_d: float
    n_ok: int
    qflag: str
    active_branch: str
    vulnerability_score: float
    needs_inspection: bool = False
    governing_node_id: str = "UNKNOWN"


class StateReconstructionService:
    def __init__(self):
        # Trailing moisture history per stack for Theil-Sen regression:
        # stack_id -> list of (timestamp, m_est)
        self.moisture_history: Dict[str, List[Tuple[datetime, float]]] = {}

    def compute_theil_sen_slope(self, stack_id: str, current_time: datetime, current_m_est: float) -> float:
        """
        Computes dM/dt over the trailing 24h window using Theil-Sen robust slope regression.
        Units: %wb · day⁻¹.
        """
        hist = self.moisture_history.setdefault(stack_id, [])
        hist.append((current_time, current_m_est))
        
        # Keep trailing 24 hours of data
        cutoff_24h = current_time - timedelta(hours=24)
        hist = [p for p in hist if p[0] >= cutoff_24h]
        self.moisture_history[stack_id] = hist
        
        if len(hist) < 4:
            # Not enough points for a robust 24h regression yet
            return 0.0
            
        # Convert timestamps to fractional days relative to t0
        t0 = hist[0][0]
        x_days = np.array([(p[0] - t0).total_seconds() / 86400.0 for p in hist])
        y_moisture = np.array([p[1] for p in hist])
        
        # Guard against zero variance in x
        if np.max(x_days) - np.min(x_days) < 0.01:
            return 0.0
            
        try:
            res = theilslopes(y_moisture, x_days, alpha=0.95)
            slope = float(res.slope)
            return round(slope, 3)
        except Exception:
            return 0.0

    def assemble_fused_record(
        self,
        stack: SyntheticStack,
        screening_res: ScreeningResult,
        isotherm_res: IsothermResult,
        mra_val: float,
        weather: WeatherState,
        current_time: datetime,
    ) -> FusedStateRecord:
        """
        Fuses all screened sensors, isotherm results, robust derivative, MRA, and weather scalars
        into a strict, auditable FusedStateRecord.
        """
        # Calculate robust Theil-Sen slope over trailing 24h
        dm_dt = self.compute_theil_sen_slope(
            stack_id=stack.stack_id,
            current_time=current_time,
            current_m_est=isotherm_res.m_est_percent,
        )
        
        record = FusedStateRecord(
            stack_id=stack.stack_id,
            ts=current_time,
            aw_max=isotherm_res.aw_max,
            m_est=isotherm_res.m_est_percent,
            dm_dt_24h=dm_dt,
            t_core=isotherm_res.t_core_stack_max,
            t_amb_ma24=weather.temp_amb_ma24,
            mra=mra_val,
            r72=weather.r72_mm,
            p_rain=weather.p_rain,
            rhf=weather.rh_forecast_mean,
            mass_t=stack.tonnage_m,
            age_d=round(stack.get_age_days(current_time), 1),
            n_ok=screening_res.n_ok,
            qflag=screening_res.qflag,
            active_branch=isotherm_res.active_branch,
            vulnerability_score=round(stack.rubric.total_score, 2),
            needs_inspection=screening_res.needs_inspection,
            governing_node_id=isotherm_res.governing_node_id,
        )
        return record
