"""
Main Backend Application Entrypoint & System Orchestrator.
Integrates Modules 1, 2, 3, and 4 into an unified reactive service.
Initializes FastAPI, SQLite persistence, Simulation Clock, and WebSocket broadcaster.
"""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.db.database import init_db, save_fused_record, get_stack_history
from backend.simulator.node_model import SyntheticStack, VulnerabilityRubric
from backend.simulator.weather_synth import WeatherSynthesizer, WeatherState
from backend.simulator.stack_lifecycle import YardManager
from backend.simulator.scenarios import ScenarioEngine
from backend.simulator.clock import SimulationClock
from backend.gateway.fault_screening import FaultScreeningService, ScreeningResult
from backend.gateway.isotherm import IsothermInversionService, IsothermResult
from backend.gateway.mra import MouldRiskAccumulator
from backend.gateway.state_record import StateReconstructionService, FusedStateRecord
from backend.gateway.weather_client import WeatherGatewayClient
from backend.engine.weights_store import WeightsStore, SubIndexWeights, AnchorsConfig, AlertLadderConfig
from backend.engine.sub_indices import SubIndexCalculator, SubIndexVector
from backend.engine.epi import EPIEngine, EPIScore, ActiveAlert
from backend.engine.dispatch import DispatchOptimizer, DispatchPlan
from backend.api.ws import ws_manager
from backend.api.schemas import (
    YardOverviewSchema,
    StackSummarySchema,
    StackDetailSchema,
    NodeDetailSchema,
    VulnerabilityAuditRequest,
    MaintenanceLogRequest,
    SimControlRequest,
    SeasonReportSchema,
    WebSocketBroadcastMessage,
)
from backend.api.routes import router as api_router


class SystemOrchestrator:
    def __init__(self):
        # 1. State stores & parameters
        self.weights_store = WeightsStore()
        curr_cfg = self.weights_store.current
        self.sub_index_calc = SubIndexCalculator(curr_cfg.anchors)
        self.epi_engine = EPIEngine(
            weights=curr_cfg.weights,
            anchors=curr_cfg.anchors,
            ladder_config=curr_cfg.alert_ladder,
            config_version_id=curr_cfg.version_id,
        )
        self.dispatch_opt = DispatchOptimizer()

        # 2. Simulator & Yard
        self.weather_synth = WeatherSynthesizer(base_temp_c=29.5, base_rh_pct=68.0)
        self.weather_client = WeatherGatewayClient(self.weather_synth)
        self.yard_manager = YardManager("YARD-THANJAVUR-01")
        
        # 3. Gateway services
        self.fault_screening = FaultScreeningService()
        self.isotherm_service = IsothermInversionService()
        self.mra_service = MouldRiskAccumulator(
            tau_days=14.0,
            fungal_threshold_aw=0.65,
            q10=2.0,
            mra_crit=curr_cfg.anchors.mra_crit,
        )
        self.state_recon = StateReconstructionService()

        # 4. Simulation Clock
        start_time = datetime(2026, 9, 15, 6, 0, 0, tzinfo=timezone.utc)
        self.clock = SimulationClock(start_time=start_time, wall_seconds_per_tick=1.0)
        self.clock.register_tick_callback(self.advance_tick)

        # 5. Caches of latest state per stack
        self.latest_weather: Optional[WeatherState] = None
        self.latest_screenings: Dict[str, ScreeningResult] = {}
        self.latest_isotherms: Dict[str, IsothermResult] = {}
        self.latest_fused_records: Dict[str, FusedStateRecord] = {}
        self.latest_sub_indices: Dict[str, SubIndexVector] = {}
        self.latest_epi_scores: Dict[str, EPIScore] = {}
        self.current_dispatch_plan: Optional[DispatchPlan] = None
        self.supervisor_overrides: Dict[str, str] = {}  # stack_id -> reason_code
        self.maintenance_logs: List[Dict[str, Any]] = []

        # Initialize yard
        self.yard_manager.initialize_standard_yard(start_time)
        ScenarioEngine.setup_default_yard(self.yard_manager.stacks, self.weather_synth, start_time)

    async def initialize(self) -> None:
        """Run initial warm-up tick and start clock."""
        init_db()
        await self.advance_tick(self.clock.sim_time, 15.0)

    async def advance_tick(self, sim_time: datetime, dt_minutes: float) -> None:
        """Core simulation & pipeline execution loop running on every 15-min tick."""
        # 1. Weather
        self.latest_weather = await self.weather_client.fetch_weather(sim_time, dt_minutes)

        # 2. Process each stack in yard
        precedence_dag = {}
        for sid, stack in self.yard_manager.stacks.items():
            if stack.blocked_by_stack_id:
                precedence_dag[sid] = stack.blocked_by_stack_id

            if stack.is_evacuated:
                continue

            # Forward physics
            stack.advance_physics(
                dt_minutes=dt_minutes,
                ambient_rh_pct=self.latest_weather.ambient_rh_pct,
                ambient_temp_c=self.latest_weather.ambient_temp_c,
                is_raining=self.latest_weather.is_raining,
                rain_rate_mm_h=self.latest_weather.rain_rate_mm_h,
                amb_temp_24h_ma=self.latest_weather.temp_amb_ma24,
                current_time=sim_time,
            )

            # Emit telemetry
            raw_readings = stack.emit_telemetry(sim_time)

            # Screen telemetry
            screen_res = self.fault_screening.screen_stack_readings(sid, raw_readings, sim_time)
            self.latest_screenings[sid] = screen_res

            # Isotherm inversion with branch hysteresis
            prev_dM = self.latest_fused_records[sid].dm_dt_24h if sid in self.latest_fused_records else 0.0
            isotherm_res = self.isotherm_service.evaluate_stack_moisture(
                stack_id=sid,
                surviving_readings=screen_res.surviving_readings,
                trailing_dM_dt=prev_dM,
            )
            self.latest_isotherms[sid] = isotherm_res

            # MRA numerical integration
            mra_val = self.mra_service.add_epoch_and_integrate(
                stack_id=sid,
                timestamp=sim_time,
                aw_max=isotherm_res.aw_max,
                temp_core_c=isotherm_res.t_core_at_worst_case,
            )

            # Fused State Record assembly & persistence
            fused_rec = self.state_recon.assemble_fused_record(
                stack=stack,
                screening_res=screen_res,
                isotherm_res=isotherm_res,
                mra_val=mra_val,
                weather=self.latest_weather,
                current_time=sim_time,
            )
            self.latest_fused_records[sid] = fused_rec
            save_fused_record(fused_rec.model_dump())

            # Sub-indices & EPI calculation
            s_vec = self.sub_index_calc.compute(fused_rec)
            self.latest_sub_indices[sid] = s_vec
            epi_score = self.epi_engine.compute_epi(fused_rec, s_vec)
            self.latest_epi_scores[sid] = epi_score

            # Alert Ladder evaluation
            reason_en, reason_ta = self.dispatch_opt.generate_reasons(fused_rec, epi_score)
            self.epi_engine.evaluate_alert_ladder(
                epi_score=epi_score,
                governing_node_id=isotherm_res.governing_node_id,
                reason_en=reason_en,
                reason_ta=reason_ta,
            )

        # 3. Dispatch Plan optimization
        self.current_dispatch_plan = self.dispatch_opt.optimize_dispatch(
            current_time=sim_time,
            records=self.latest_fused_records,
            epi_scores=self.latest_epi_scores,
            truck_capacity_mt=self.yard_manager.daily_truck_capacity_mt,
            precedence_dag=precedence_dag,
            overrides=self.supervisor_overrides,
        )

        # 4. Broadcast live WebSocket update
        try:
            overview = self.get_yard_overview()
            msg = WebSocketBroadcastMessage(
                event_type="TICK",
                timestamp=sim_time,
                data={
                    "yard": overview.model_dump(),
                    "dispatch": self.current_dispatch_plan.model_dump() if self.current_dispatch_plan else None,
                    "active_alerts_count": len([a for a in self.epi_engine.alert_history if a.is_active]),
                },
            )
            await ws_manager.broadcast(msg)
        except Exception as e:
            print(f"[Orchestrator] Error broadcasting tick: {e}")

    def get_yard_overview(self) -> YardOverviewSchema:
        stack_summaries = []
        at_risk = 0
        for sid, stack in self.yard_manager.stacks.items():
            fused = self.latest_fused_records.get(sid)
            epi = self.latest_epi_scores.get(sid)
            if not fused or not epi:
                continue
            if epi.final_epi >= 50.0:
                at_risk += 1
            stack_summaries.append(
                StackSummarySchema(
                    stack_id=sid,
                    row_id=stack.row_id,
                    position_index=stack.position_index,
                    tonnage_mt=stack.tonnage_m,
                    age_days=round(stack.get_age_days(self.clock.sim_time), 1),
                    assigned_scenario=stack.assigned_scenario,
                    is_evacuated=stack.is_evacuated,
                    blocks_stack_id=stack.blocks_stack_id,
                    blocked_by_stack_id=stack.blocked_by_stack_id,
                    current_epi=epi.final_epi,
                    band=epi.band,
                    m_est=fused.m_est,
                    aw_max=fused.aw_max,
                    t_core=fused.t_core,
                    dm_dt_24h=fused.dm_dt_24h,
                    n_ok=fused.n_ok,
                    qflag=fused.qflag,
                    needs_inspection=fused.needs_inspection,
                    vulnerability_score=fused.vulnerability_score,
                    active_branch=fused.active_branch,
                    override_fired=epi.override_fired,
                )
            )

        w = self.latest_weather or self.weather_synth.advance(self.clock.sim_time)
        return YardOverviewSchema(
            yard_id=self.yard_manager.yard_id,
            sim_time=self.clock.sim_time,
            is_clock_running=self.clock.is_running,
            speed_multiplier=self.clock.speed_multiplier,
            weather_mode=w.feed_mode,
            weather_stale=w.is_stale,
            ambient_temp=w.ambient_temp_c,
            ambient_rh=w.ambient_rh_pct,
            is_raining=w.is_raining,
            r72_mm=w.r72_mm,
            p_rain=w.p_rain,
            stacks_count=len(self.yard_manager.stacks),
            at_risk_count=at_risk,
            stacks=stack_summaries,
        )

    def get_stack_detail(self, stack_id: str) -> Optional[StackDetailSchema]:
        stack = self.yard_manager.stacks.get(stack_id)
        fused = self.latest_fused_records.get(stack_id)
        epi = self.latest_epi_scores.get(stack_id)
        screening = self.latest_screenings.get(stack_id)
        if not stack or not fused or not epi:
            return None

        # Build node details
        node_details = []
        for nid, node in stack.nodes.items():
            screened = screening.all_screened_nodes.get(nid) if screening else None
            node_details.append(
                NodeDetailSchema(
                    node_id=nid,
                    stack_id=stack_id,
                    position=node.position,
                    health_state=node.health_state,
                    battery_voltage=round(node.battery_voltage_proxy, 3),
                    erh_observed=round(screened.erh if screened else node.true_water_activity * 100.0, 2),
                    temp_observed=round(screened.temp_c if screened else node.true_temperature, 2),
                    temp_core_observed=round(screened.temp_core_c if screened else node.true_core_temperature, 2),
                    is_suspect=screened.is_suspect if screened else False,
                    is_stale=screened.is_stale if screened else False,
                    suspect_reasons=screened.suspect_reasons if screened else [],
                )
            )

        history = get_stack_history(stack_id, limit=96)
        summary = StackSummarySchema(
            stack_id=stack_id,
            row_id=stack.row_id,
            position_index=stack.position_index,
            tonnage_mt=stack.tonnage_m,
            age_days=round(stack.get_age_days(self.clock.sim_time), 1),
            assigned_scenario=stack.assigned_scenario,
            is_evacuated=stack.is_evacuated,
            blocks_stack_id=stack.blocks_stack_id,
            blocked_by_stack_id=stack.blocked_by_stack_id,
            current_epi=epi.final_epi,
            band=epi.band,
            m_est=fused.m_est,
            aw_max=fused.aw_max,
            t_core=fused.t_core,
            dm_dt_24h=fused.dm_dt_24h,
            n_ok=fused.n_ok,
            qflag=fused.qflag,
            needs_inspection=fused.needs_inspection,
            vulnerability_score=fused.vulnerability_score,
            active_branch=fused.active_branch,
            override_fired=epi.override_fired,
        )

        return StackDetailSchema(
            summary=summary,
            rubric=stack.rubric,
            nodes=node_details,
            recent_history=history,
            sub_index_breakdown=epi.sub_indices.as_dict(),
        )

    def update_stack_rubric(self, stack_id: str, req: VulnerabilityAuditRequest) -> bool:
        stack = self.yard_manager.stacks.get(stack_id)
        if not stack:
            return False
        stack.rubric = VulnerabilityRubric(
            tarpaulin_condition=req.tarpaulin_condition,
            dunnage_plinth=req.dunnage_plinth,
            drainage_proximity=req.drainage_proximity,
            position_in_row=req.position_in_row,
            residence_time=req.residence_time,
        )
        return True

    def get_current_dispatch_plan(self) -> DispatchPlan:
        if self.current_dispatch_plan:
            return self.current_dispatch_plan
        return self.dispatch_opt.optimize_dispatch(
            current_time=self.clock.sim_time,
            records=self.latest_fused_records,
            epi_scores=self.latest_epi_scores,
            truck_capacity_mt=self.yard_manager.daily_truck_capacity_mt,
        )

    def apply_dispatch_override(self, stack_id: str, code: str, notes: Optional[str] = None) -> bool:
        if stack_id not in self.yard_manager.stacks:
            return False
        self.supervisor_overrides[stack_id] = code
        # Recompute dispatch plan immediately
        precedence_dag = {sid: s.blocked_by_stack_id for sid, s in self.yard_manager.stacks.items() if s.blocked_by_stack_id}
        self.current_dispatch_plan = self.dispatch_opt.optimize_dispatch(
            current_time=self.clock.sim_time,
            records=self.latest_fused_records,
            epi_scores=self.latest_epi_scores,
            truck_capacity_mt=self.yard_manager.daily_truck_capacity_mt,
            precedence_dag=precedence_dag,
            overrides=self.supervisor_overrides,
        )
        return True

    def get_all_nodes_health(self) -> List[NodeDetailSchema]:
        results = []
        for sid, stack in self.yard_manager.stacks.items():
            screening = self.latest_screenings.get(sid)
            for nid, node in stack.nodes.items():
                screened = screening.all_screened_nodes.get(nid) if screening else None
                results.append(
                    NodeDetailSchema(
                        node_id=nid,
                        stack_id=sid,
                        position=node.position,
                        health_state=node.health_state,
                        battery_voltage=round(node.battery_voltage_proxy, 3),
                        erh_observed=round(screened.erh if screened else node.true_water_activity * 100.0, 2),
                        temp_observed=round(screened.temp_c if screened else node.true_temperature, 2),
                        temp_core_observed=round(screened.temp_core_c if screened else node.true_core_temperature, 2),
                        is_suspect=screened.is_suspect if screened else False,
                        is_stale=screened.is_stale if screened else False,
                        suspect_reasons=screened.suspect_reasons if screened else [],
                    )
                )
        return results

    def log_node_maintenance(self, req: MaintenanceLogRequest) -> Dict[str, Any]:
        entry = {
            "node_id": req.node_id,
            "stack_id": req.stack_id,
            "action_type": req.action_type,
            "notes": req.notes,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "operator_role": req.operator_role,
        }
        self.maintenance_logs.append(entry)
        
        # Reset node if replaced
        stack = self.yard_manager.stacks.get(req.stack_id)
        if stack and req.node_id in stack.nodes:
            node = stack.nodes[req.node_id]
            node.health_state = "ok"
            node.battery_voltage_proxy = 3.60
            node.condensation_fault_active = False
            node.stuck_at_fault_active = False
            node.dropout_active = False
            
        return entry

    def get_season_report(self) -> SeasonReportSchema:
        top_6_ids = [item.stack_id for item in (self.current_dispatch_plan.queue[:6] if self.current_dispatch_plan else [])]
        prec_6 = self.yard_manager.calculate_precision_at_k(top_6_ids)
        avg_lead = (
            sum(self.yard_manager.lead_times_hours) / len(self.yard_manager.lead_times_hours)
            if self.yard_manager.lead_times_hours
            else 48.0
        )
        
        # Node survival calculation
        total_nodes = sum(len(s.nodes) for s in self.yard_manager.stacks.values())
        healthy_nodes = sum(
            1 for s in self.yard_manager.stacks.values()
            for n in s.nodes.values() if n.health_state == "ok" and not n.dropout_active
        )
        survival_pct = round((healthy_nodes / max(1, total_nodes)) * 100.0, 1)

        return SeasonReportSchema(
            total_tonnes_evacuated=round(self.yard_manager.total_tonnes_evacuated, 1),
            tonnes_by_band=self.yard_manager.tonnes_by_band,
            avoided_breaches_count=self.yard_manager.avoided_breaches_count,
            average_lead_time_hours=round(avg_lead, 1),
            node_survival_rate_percent=survival_pct,
            optimization_improvement_gain=self.current_dispatch_plan.optimization_improvement_gain if self.current_dispatch_plan else 0.0,
            precision_at_6=round(prec_6, 2),
            evacuated_stacks=self.yard_manager.evacuated_stacks,
        )

    def get_alerts_payload(self) -> Dict[str, Any]:
        return {
            "active_alerts": [a.model_dump() for a in self.epi_engine.alert_history if a.is_active],
            "total_alerts_count": len(self.epi_engine.alert_history),
            "simulated_sms_inbox": [
                {
                    "alert_id": a.alert_id,
                    "stack_id": a.stack_id,
                    "band": a.band,
                    "timestamp": a.triggered_at.isoformat(),
                    "sms_body_ta": f"எச்சரிக்கை: {a.stack_id} நிலை {a.band}. {a.reason_ta}",
                    "sms_body_en": f"ALERT: {a.stack_id} status {a.band}. {a.reason_en}",
                    "recipient": "Yard Supervisor (+91-9443XXXXXX)",
                }
                for a in self.epi_engine.alert_history
                if a.simulated_sms_sent
            ],
        }

    def get_settings_payload(self) -> Dict[str, Any]:
        curr = self.weights_store.current
        return {
            "version_id": curr.version_id,
            "weights": curr.weights.model_dump(),
            "anchors": curr.anchors.model_dump(),
            "alert_ladder": curr.alert_ladder.model_dump(),
            "isotherm_parameters": {
                "adsorption": {"A": 502.8, "B": 16.5, "C": 41.5},
                "desorption": {"A": 591.4, "B": 16.8, "C": 35.7},
            },
            "history_versions": [v.model_dump() for v in self.weights_store.versions],
        }

    def apply_new_weights(self, weights: SubIndexWeights, author: str, rationale: str):
        new_v = self.weights_store.create_version(weights=weights, author=author, rationale=rationale)
        # Update active engine weights
        self.epi_engine.weights = new_v.weights
        self.epi_engine.config_version_id = new_v.version_id
        return new_v

    def get_sensitivity_analysis(self) -> Dict[str, Any]:
        sub_vecs = {sid: s.as_dict() for sid, s in self.latest_sub_indices.items()}
        return self.weights_store.compute_sensitivity_analysis(sub_vecs, perturbation_fraction=0.30)

    async def handle_sim_control(self, req: SimControlRequest) -> Dict[str, Any]:
        if req.action == "play":
            self.clock.play()
        elif req.action == "pause":
            self.clock.pause()
        elif req.action == "step":
            await self.clock.step()
        elif req.action == "reset":
            self.clock.reset()
            self.yard_manager.initialize_standard_yard(self.clock.sim_time)
            ScenarioEngine.setup_default_yard(self.yard_manager.stacks, self.weather_synth, self.clock.sim_time)
            await self.advance_tick(self.clock.sim_time, 15.0)
        elif req.action == "set_speed":
            if req.speed_multiplier:
                self.clock.set_speed(req.speed_multiplier)
        elif req.action == "assign_scenario":
            if req.stack_id and req.scenario_name:
                stack = self.yard_manager.stacks.get(req.stack_id)
                if stack:
                    ScenarioEngine.apply_scenario_to_stack(
                        stack, req.scenario_name, self.weather_synth, self.clock.sim_time
                    )
        elif req.action == "toggle_weather_mode":
            mode = req.weather_mode or ("live" if self.weather_client.live_enabled else "synthetic")
            self.weather_client.set_live_mode(mode == "live")
        elif req.action == "toggle_weather_fault":
            self.weather_synth.feed_down_fault = not self.weather_synth.feed_down_fault

        return {
            "status": "success",
            "action": req.action,
            "is_running": self.clock.is_running,
            "speed_multiplier": self.clock.speed_multiplier,
            "sim_time": self.clock.sim_time.isoformat(),
        }


orchestrator = SystemOrchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize orchestrator and database
    await orchestrator.initialize()
    # Start simulation clock playing by default (1 sec wall time per 15-min sim tick)
    orchestrator.clock.play()
    yield
    # Shutdown: Pause simulation clock
    orchestrator.clock.pause()


app = FastAPI(
    title="Smart Grain Stack Evacuation Platform API",
    version="1.0.0",
    description="Software-Only Gateway & Ingestion, Physics Inference, EPI Engine, and Dispatch Optimizer",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send immediate initial state
        overview = orchestrator.get_yard_overview()
        dispatch = orchestrator.get_current_dispatch_plan()
        msg = WebSocketBroadcastMessage(
            event_type="TICK",
            timestamp=orchestrator.clock.sim_time,
            data={
                "yard": overview.model_dump(),
                "dispatch": dispatch.model_dump() if dispatch else None,
                "active_alerts_count": len([a for a in orchestrator.epi_engine.alert_history if a.is_active]),
            },
        )
        await websocket.send_text(msg.model_dump_json())
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
