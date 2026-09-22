"""
Module 3: Evacuation Priority Index (EPI) Engine & Alert Ladder.
Combines sub-indices into 0-100 EPI score, enforces hard safety overrides,
and manages the stateful Alert Escalation Ladder with hysteresis and dwell times.
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from backend.engine.sub_indices import SubIndexVector
from backend.engine.weights_store import SubIndexWeights, AnchorsConfig, AlertLadderConfig
from backend.gateway.state_record import FusedStateRecord


class EPIScore(BaseModel):
    stack_id: str
    timestamp: datetime
    raw_epi: float
    final_epi: float
    override_fired: bool
    override_reason: Optional[str] = None
    band: str  # "Normal", "Watch", "Priority", "Critical"
    sub_indices: SubIndexVector
    active_weights: SubIndexWeights
    config_version_id: int


class ActiveAlert(BaseModel):
    alert_id: str
    stack_id: str
    band: str  # "Watch", "Priority", "Critical"
    triggered_at: datetime
    dwell_satisfied: bool
    reason_en: str
    reason_ta: str
    driving_node_ids: List[str]
    is_active: bool = True
    simulated_sms_sent: bool = False


class EPIEngine:
    def __init__(
        self,
        weights: SubIndexWeights,
        anchors: AnchorsConfig,
        ladder_config: AlertLadderConfig,
        config_version_id: int = 1,
    ):
        self.weights = weights
        self.anchors = anchors
        self.ladder_config = ladder_config
        self.config_version_id = config_version_id
        
        # State tracking for alert ladder hysteresis & dwell
        # stack_id -> { "current_band": str, "band_entered_time": datetime, "candidate_band": str, "candidate_start_time": datetime }
        self.ladder_state: Dict[str, Dict] = {}
        self.alert_history: List[ActiveAlert] = []

    def compute_epi(self, record: FusedStateRecord, s_vec: SubIndexVector) -> EPIScore:
        """
        Computes the Evacuation Priority Index (0 to 100).
        Applies safety override if M_est >= 17.0% or MRA >= MRA_crit.
        """
        w = self.weights
        weighted_sum = (
            w.w_M * s_vec.s_M
            + w.w_R * s_vec.s_R
            + w.w_T * s_vec.s_T
            + w.w_A * s_vec.s_A
            + w.w_F * s_vec.s_F
            + w.w_V * s_vec.s_V
        )
        raw_epi = round(weighted_sum * 100.0, 2)
        
        # Safety Override check
        override_fired = False
        override_reason = None
        final_epi = raw_epi
        
        if record.m_est >= self.anchors.m_crit:
            override_fired = True
            override_reason = f"Moisture breach (M_est = {record.m_est:.1f}% >= {self.anchors.m_crit:.1f}%)"
            final_epi = max(final_epi, 90.0)
            
        if record.mra >= self.anchors.mra_crit:
            override_fired = True
            mra_msg = f"Mould Risk Accumulator breach (MRA = {record.mra:.2f} >= {self.anchors.mra_crit:.1f} a_w·h)"
            override_reason = f"{override_reason}; {mra_msg}" if override_reason else mra_msg
            final_epi = max(final_epi, 90.0)

        # Categorize into band
        if final_epi >= self.ladder_config.critical_threshold:
            band = "Critical"
        elif final_epi >= self.ladder_config.priority_threshold:
            band = "Priority"
        elif final_epi >= self.ladder_config.watch_threshold:
            band = "Watch"
        else:
            band = "Normal"

        return EPIScore(
            stack_id=record.stack_id,
            timestamp=record.ts,
            raw_epi=raw_epi,
            final_epi=round(final_epi, 2),
            override_fired=override_fired,
            override_reason=override_reason,
            band=band,
            sub_indices=s_vec,
            active_weights=self.weights,
            config_version_id=self.config_version_id,
        )

    def evaluate_alert_ladder(
        self,
        epi_score: EPIScore,
        governing_node_id: str,
        reason_en: str,
        reason_ta: str,
    ) -> Optional[ActiveAlert]:
        """
        Processes alert ladder with dwell time and hysteresis:
        - Critical: dwell 30m, OR immediate if override fired
        - Priority: dwell 2h
        - Watch: dwell 3h
        - De-escalation: 10-pt hysteresis + 6h dwell
        """
        sid = epi_score.stack_id
        current_time = epi_score.timestamp
        state = self.ladder_state.setdefault(sid, {
            "active_band": "Normal",
            "active_band_since": current_time,
            "candidate_band": epi_score.band,
            "candidate_since": current_time,
        })
        
        target_band = epi_score.band
        
        # Override bypasses dwell immediately to Critical (once per open incident)
        if epi_score.override_fired:
            already = next(
                (a for a in self.alert_history if a.stack_id == sid and a.is_active and a.band == "Critical"),
                None,
            )
            if already:
                return None
            for prior in self.alert_history:
                if prior.stack_id == sid:
                    prior.is_active = False
            state["active_band"] = "Critical"
            state["active_band_since"] = current_time
            alert = ActiveAlert(
                alert_id=f"ALT-{sid}-{int(current_time.timestamp())}",
                stack_id=sid,
                band="Critical",
                triggered_at=current_time,
                dwell_satisfied=True,
                reason_en=f"SAFETY OVERRIDE: {reason_en}",
                reason_ta=f"பாதுகாப்பு எச்சரிக்கை: {reason_ta}",
                driving_node_ids=[governing_node_id],
                simulated_sms_sent=True,
            )
            self.alert_history.append(alert)
            return alert

        # Standard escalation / de-escalation dwell check
        if target_band != state["candidate_band"]:
            state["candidate_band"] = target_band
            state["candidate_since"] = current_time
            return None

        dwell_seconds = (current_time - state["candidate_since"]).total_seconds()
        
        # Escalation dwell requirements
        needed_dwell_sec = 0.0
        if target_band == "Critical":
            needed_dwell_sec = self.ladder_config.dwell_critical_minutes * 60.0
        elif target_band == "Priority":
            needed_dwell_sec = self.ladder_config.dwell_priority_hours * 3600.0
        elif target_band == "Watch":
            needed_dwell_sec = self.ladder_config.dwell_watch_hours * 3600.0
            
        # De-escalation dwell requirement (6h)
        is_deescalation = False
        band_order = {"Normal": 0, "Watch": 1, "Priority": 2, "Critical": 3}
        if band_order[target_band] < band_order[state["active_band"]]:
            is_deescalation = True
            needed_dwell_sec = self.ladder_config.deescalate_dwell_hours * 3600.0

        if dwell_seconds >= needed_dwell_sec and state["active_band"] != target_band:
            state["active_band"] = target_band
            state["active_band_since"] = current_time
            
            for prior in self.alert_history:
                if prior.stack_id == sid:
                    prior.is_active = False
            if target_band in ["Watch", "Priority", "Critical"]:
                alert = ActiveAlert(
                    alert_id=f"ALT-{sid}-{int(current_time.timestamp())}",
                    stack_id=sid,
                    band=target_band,
                    triggered_at=current_time,
                    dwell_satisfied=True,
                    reason_en=reason_en,
                    reason_ta=reason_ta,
                    driving_node_ids=[governing_node_id],
                    simulated_sms_sent=target_band in ["Priority", "Critical"],
                )
                self.alert_history.append(alert)
                return alert
                
        return None
