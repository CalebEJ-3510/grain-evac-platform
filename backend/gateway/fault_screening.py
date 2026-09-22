"""
Module 2: Ingestion & Fault Screening.
Performs strict multi-stage screening on raw node telemetry:
1. Time alignment to nearest 15-minute slot; stale flag if gap > 2 cycles.
2. Plausible range checks for RH and Temperature.
3. Stuck-at detection (variance over trailing 6h below floor).
4. Rate-of-change plausibility (sudden jump > 15% RH in 15 mins).
5. Intra-stack cluster neighbour consistency via robust median and MAD z-score.
6. Surviving node counting (n_ok) and 'needs_inspection' flagging if n_ok < 2.
"""

from __future__ import annotations
import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from pydantic import BaseModel
from backend.simulator.node_model import NodeReading


class ScreenedReading(BaseModel):
    node_id: str
    stack_id: str
    aligned_timestamp: datetime
    raw_timestamp: datetime
    erh: float
    water_activity: float  # erh / 100.0
    temp_c: float
    temp_core_c: float
    battery_voltage: float
    is_suspect: bool = False
    is_stale: bool = False
    suspect_reasons: List[str] = []


class ScreeningResult(BaseModel):
    stack_id: str
    aligned_timestamp: datetime
    surviving_readings: List[ScreenedReading]
    n_ok: int
    qflag: str  # "OK", "DEGRADED", "SUSPECT", "CRITICAL_FAULT"
    needs_inspection: bool = False
    all_screened_nodes: Dict[str, ScreenedReading] = {}


class FaultScreeningService:
    def __init__(
        self,
        rh_min: float = 0.0,
        rh_max: float = 100.0,
        temp_min: float = -5.0,
        temp_max: float = 60.0,
        stuck_at_variance_floor: float = 1e-4,
        max_rh_delta_per_15min: float = 15.0,
        outlier_mad_threshold: float = 3.0,
    ):
        self.rh_min = rh_min
        self.rh_max = rh_max
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.stuck_at_variance_floor = stuck_at_variance_floor
        self.max_rh_delta = max_rh_delta_per_15min
        self.outlier_mad_threshold = outlier_mad_threshold
        
        # Node history: node_id -> list of (timestamp, erh, temp)
        self.node_history: Dict[str, List[Tuple[datetime, float, float]]] = {}
        # Last accepted reading time per node
        self.last_accepted_time: Dict[str, datetime] = {}

    def align_timestamp(self, ts: datetime) -> datetime:
        """Snaps timestamp to nearest 15-minute grid slot."""
        minute = ts.minute
        remainder = minute % 15
        if remainder < 7.5:
            rounded_minute = minute - remainder
            add_minutes = 0
        else:
            rounded_minute = (minute - remainder + 15) % 60
            add_minutes = 15 if (minute - remainder + 15) >= 60 else 0
            
        aligned = ts.replace(minute=rounded_minute, second=0, microsecond=0)
        if add_minutes > 0:
            aligned += timedelta(hours=1)
        return aligned

    def screen_stack_readings(
        self,
        stack_id: str,
        readings: List[NodeReading],
        current_nominal_time: datetime,
    ) -> ScreeningResult:
        """
        Screens all incoming readings for a single stack at the current nominal time.
        """
        aligned_slot = self.align_timestamp(current_nominal_time)
        screened_nodes: Dict[str, ScreenedReading] = {}
        
        for r in readings:
            suspect_reasons = []
            is_suspect = False
            is_stale = False
            
            # 1. Stale check (gap since last accepted reading > 2 cycles = 30 minutes)
            last_time = self.last_accepted_time.get(r.node_id)
            if last_time and (r.timestamp - last_time).total_seconds() > 1800:
                is_stale = True
                suspect_reasons.append("stale_transmission_gap")
                
            # 2. Range check
            if not (self.rh_min <= r.erh_observed <= self.rh_max):
                is_suspect = True
                suspect_reasons.append(f"rh_out_of_bounds_{r.erh_observed:.1f}")
                
            if not (self.temp_min <= r.temp_observed <= self.temp_max):
                is_suspect = True
                suspect_reasons.append(f"temp_out_of_bounds_{r.temp_observed:.1f}")

            # Retrieve node history
            history = self.node_history.setdefault(r.node_id, [])
            
            # 3. Rate of change check (RH delta in 15 mins > 15%)
            if history:
                prev_ts, prev_erh, _ = history[-1]
                delta_minutes = (r.timestamp - prev_ts).total_seconds() / 60.0
                if 0 < delta_minutes <= 25:
                    rh_step = abs(r.erh_observed - prev_erh)
                    if rh_step > self.max_rh_delta:
                        is_suspect = True
                        suspect_reasons.append(f"rapid_rh_step_{rh_step:.1f}")

            # 4. Stuck-at check (variance over trailing 6 hours below threshold)
            # Add current point to history temporarily for variance check
            cutoff_6h = r.timestamp - timedelta(hours=6)
            recent_points = [p for p in history if p[0] >= cutoff_6h]
            if len(recent_points) >= 12:  # at least ~3 hours of points
                rh_values = [p[1] for p in recent_points] + [r.erh_observed]
                var_rh = float(np.var(rh_values))
                if var_rh < self.stuck_at_variance_floor:
                    is_suspect = True
                    suspect_reasons.append(f"stuck_at_sensor_freeze_var_{var_rh:.6f}")

            # Record reading
            sr = ScreenedReading(
                node_id=r.node_id,
                stack_id=stack_id,
                aligned_timestamp=aligned_slot,
                raw_timestamp=r.timestamp,
                erh=r.erh_observed,
                water_activity=max(0.01, min(0.999, r.erh_observed / 100.0)),
                temp_c=r.temp_observed,
                temp_core_c=r.temp_core_observed,
                battery_voltage=r.battery_voltage,
                is_suspect=is_suspect,
                is_stale=is_stale,
                suspect_reasons=suspect_reasons,
            )
            screened_nodes[r.node_id] = sr
            
            # If healthy, update last accepted time and history
            if not is_suspect and not is_stale:
                self.last_accepted_time[r.node_id] = r.timestamp
                history.append((r.timestamp, r.erh_observed, r.temp_observed))
                # Trim history to 24 hours
                cutoff_24h = r.timestamp - timedelta(hours=24)
                self.node_history[r.node_id] = [p for p in history if p[0] >= cutoff_24h]

        # 5. Intra-stack cluster neighbour consistency check
        # Compare each surviving node against the robust median of the stack cluster
        healthy_candidates = [sr for sr in screened_nodes.values() if not sr.is_suspect and not sr.is_stale]
        if len(healthy_candidates) >= 3:
            erh_vals = np.array([sr.erh for sr in healthy_candidates])
            median_erh = float(np.median(erh_vals))
            # Median Absolute Deviation (MAD)
            mad = float(np.median(np.abs(erh_vals - median_erh)))
            mad = max(0.5, mad)  # Avoid division by zero
            
            for sr in healthy_candidates:
                robust_z = abs(sr.erh - median_erh) / (1.4826 * mad)
                if robust_z > self.outlier_mad_threshold and abs(sr.erh - median_erh) > 10.0:
                    sr.is_suspect = True
                    sr.suspect_reasons.append(f"cluster_outlier_z_{robust_z:.2f}")

        # 6. Count surviving valid nodes
        surviving = [sr for sr in screened_nodes.values() if not sr.is_suspect and not sr.is_stale]
        n_ok = len(surviving)
        needs_inspection = n_ok < 2
        
        if n_ok >= 3:
            qflag = "OK"
        elif n_ok == 2:
            qflag = "DEGRADED"
        elif n_ok == 1:
            qflag = "SUSPECT"
        else:
            qflag = "CRITICAL_FAULT"

        return ScreeningResult(
            stack_id=stack_id,
            aligned_timestamp=aligned_slot,
            surviving_readings=surviving,
            n_ok=n_ok,
            qflag=qflag,
            needs_inspection=needs_inspection,
            all_screened_nodes=screened_nodes,
        )
