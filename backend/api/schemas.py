"""
Module 4: API Schemas (Pydantic v2).
Defines contracts for all REST endpoints and WebSocket events:
- Yard overview, Stack summaries, Detail views
- Loading queue & Dispatch override payloads
- Node health & Maintenance logging
- AHP matrix & sensitivity requests
- Simulation clock & scenario controls
- WebSocket live broadcast payloads
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from backend.simulator.node_model import VulnerabilityRubric
from backend.engine.weights_store import SubIndexWeights, AnchorsConfig, AlertLadderConfig
from backend.engine.dispatch import QueueItem, DispatchPlan
from backend.engine.epi import EPIScore, ActiveAlert


class StackSummarySchema(BaseModel):
    stack_id: str
    row_id: str
    position_index: int
    tonnage_mt: float
    age_days: float
    assigned_scenario: str
    is_evacuated: bool
    blocks_stack_id: Optional[str]
    blocked_by_stack_id: Optional[str]
    current_epi: float
    band: str
    m_est: float
    aw_max: float
    t_core: float
    dm_dt_24h: float
    n_ok: int
    qflag: str
    needs_inspection: bool
    vulnerability_score: float
    active_branch: str
    override_fired: bool


class YardOverviewSchema(BaseModel):
    yard_id: str
    sim_time: datetime
    is_clock_running: bool
    speed_multiplier: float
    weather_mode: str
    weather_stale: bool
    ambient_temp: float
    ambient_rh: float
    is_raining: bool
    r72_mm: float
    p_rain: float
    stacks_count: int
    at_risk_count: int
    stacks: List[StackSummarySchema]


class NodeDetailSchema(BaseModel):
    node_id: str
    stack_id: str
    position: str
    health_state: str
    battery_voltage: float
    erh_observed: float
    temp_observed: float
    temp_core_observed: float
    is_suspect: bool
    is_stale: bool
    suspect_reasons: List[str]


class StackDetailSchema(BaseModel):
    summary: StackSummarySchema
    rubric: VulnerabilityRubric
    nodes: List[NodeDetailSchema]
    recent_history: List[Dict[str, Any]]
    sub_index_breakdown: Dict[str, float]


class OverrideRequestSchema(BaseModel):
    stack_id: str
    override_reason_code: str = Field(..., description="e.g. VISUAL_TARPAULIN_DEFECT, ACCESS_OBSTRUCTION, TRUCK_AVAILABILITY")
    notes: Optional[str] = None


class VulnerabilityAuditRequest(BaseModel):
    tarpaulin_condition: int = Field(ge=0, le=2)
    dunnage_plinth: int = Field(ge=0, le=2)
    drainage_proximity: int = Field(ge=0, le=2)
    position_in_row: int = Field(ge=0, le=2)
    residence_time: int = Field(ge=0, le=2)


class MaintenanceLogRequest(BaseModel):
    node_id: str
    stack_id: str
    action_type: str
    notes: Optional[str] = None
    operator_role: str = "Quality Inspector"


class AHPMatrixRequest(BaseModel):
    pairwise_matrix: List[List[float]]  # 6x6 matrix


class AHPMatrixResponse(BaseModel):
    normalized_weights: List[float]
    sub_index_order: List[str] = ["s_M", "s_R", "s_T", "s_A", "s_F", "s_V"]
    lambda_max: float
    consistency_ratio: float
    is_consistent: bool


class ApplyWeightsRequest(BaseModel):
    weights: SubIndexWeights
    author: str = "Supervisor"
    rationale: str = "AHP Re-elicitation applied"


class SimControlRequest(BaseModel):
    action: Literal["play", "pause", "step", "reset", "set_speed", "assign_scenario", "toggle_weather_mode", "toggle_weather_fault"]
    speed_multiplier: Optional[float] = None
    stack_id: Optional[str] = None
    scenario_name: Optional[str] = None
    weather_mode: Optional[str] = None


class SeasonReportSchema(BaseModel):
    total_tonnes_evacuated: float
    tonnes_by_band: Dict[str, float]
    avoided_breaches_count: int
    average_lead_time_hours: float
    node_survival_rate_percent: float
    optimization_improvement_gain: float
    precision_at_6: float
    evacuated_stacks: List[Dict[str, Any]]


class WebSocketBroadcastMessage(BaseModel):
    event_type: Literal["TICK", "EPI_UPDATE", "ALERT_ESCALATION", "DISPATCH_UPDATE", "WEATHER_UPDATE"]
    timestamp: datetime
    data: Dict[str, Any]
