"""
Module 4: API Routes.
Exposes REST endpoints for:
- /api/yard: Yard Plan overview, stacks, weather
- /api/stacks/{stack_id}: Stack Detail, historical trends, rubric audit update
- /api/dispatch: Loading Queue, capacity bar, supervisor overrides
- /api/nodes: Node health, battery proxy, maintenance logging
- /api/season: Season metrics, precision@6, 2-opt gain
- /api/alerts: Active alert ladder, simulated SMS log
- /api/settings: Config store, AHP matrix elicitation, sensitivity analysis
- /api/sim: Simulation clock controls, scenario switching
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from backend.api.schemas import (
    YardOverviewSchema,
    StackSummarySchema,
    StackDetailSchema,
    NodeDetailSchema,
    DispatchPlan,
    OverrideRequestSchema,
    VulnerabilityAuditRequest,
    MaintenanceLogRequest,
    AHPMatrixRequest,
    AHPMatrixResponse,
    ApplyWeightsRequest,
    SimControlRequest,
    SeasonReportSchema,
)

router = APIRouter(prefix="/api")


def get_orchestrator():
    # Will be injected from main.py
    from backend.main import orchestrator
    return orchestrator


@router.get("/yard", response_model=YardOverviewSchema)
async def get_yard_overview(orc=Depends(get_orchestrator)):
    return orc.get_yard_overview()


@router.get("/stacks/{stack_id}", response_model=StackDetailSchema)
async def get_stack_detail(stack_id: str, orc=Depends(get_orchestrator)):
    detail = orc.get_stack_detail(stack_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Stack {stack_id} not found")
    return detail


@router.post("/stacks/{stack_id}/rubric")
async def update_vulnerability_rubric(
    stack_id: str,
    req: VulnerabilityAuditRequest,
    orc=Depends(get_orchestrator),
):
    success = orc.update_stack_rubric(stack_id, req)
    if not success:
        raise HTTPException(status_code=404, detail=f"Stack {stack_id} not found")
    return {"status": "success", "stack_id": stack_id, "updated_score": req}


@router.get("/dispatch", response_model=DispatchPlan)
async def get_dispatch_plan(orc=Depends(get_orchestrator)):
    return orc.get_current_dispatch_plan()


@router.post("/dispatch/override")
async def submit_dispatch_override(
    req: OverrideRequestSchema,
    orc=Depends(get_orchestrator),
):
    success = orc.apply_dispatch_override(req.stack_id, req.override_reason_code, req.notes)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to apply dispatch override")
    return {"status": "success", "stack_id": req.stack_id, "reason_code": req.override_reason_code}


@router.get("/nodes", response_model=List[NodeDetailSchema])
async def get_nodes_health(orc=Depends(get_orchestrator)):
    return orc.get_all_nodes_health()


@router.post("/nodes/maintenance")
async def log_node_maintenance(
    req: MaintenanceLogRequest,
    orc=Depends(get_orchestrator),
):
    res = orc.log_node_maintenance(req)
    return {"status": "success", "log": res}


@router.get("/season", response_model=SeasonReportSchema)
async def get_season_report(orc=Depends(get_orchestrator)):
    return orc.get_season_report()


@router.get("/alerts")
async def get_alerts(orc=Depends(get_orchestrator)):
    return orc.get_alerts_payload()


@router.get("/settings")
async def get_settings(orc=Depends(get_orchestrator)):
    return orc.get_settings_payload()


@router.post("/settings/ahp/solve", response_model=AHPMatrixResponse)
async def solve_ahp_matrix(
    req: AHPMatrixRequest,
    orc=Depends(get_orchestrator),
):
    weights, lambda_max, cr, consistent = orc.weights_store.solve_ahp_matrix(req.pairwise_matrix)
    return AHPMatrixResponse(
        normalized_weights=weights,
        lambda_max=lambda_max,
        consistency_ratio=cr,
        is_consistent=consistent,
    )


@router.post("/settings/weights/apply")
async def apply_weights(
    req: ApplyWeightsRequest,
    orc=Depends(get_orchestrator),
):
    new_v = orc.apply_new_weights(req.weights, req.author, req.rationale)
    return {"status": "success", "new_version_id": new_v.version_id}


@router.get("/settings/sensitivity")
async def get_sensitivity_analysis(orc=Depends(get_orchestrator)):
    return orc.get_sensitivity_analysis()


@router.post("/sim/control")
async def control_simulation(
    req: SimControlRequest,
    orc=Depends(get_orchestrator),
):
    return await orc.handle_sim_control(req)
