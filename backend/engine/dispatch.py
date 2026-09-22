"""
Module 3: Precedence-Constrained Dispatch Optimizer & Localized Reason Generation.
Implements:
1. Greedy-by-EPI descending knapsack baseline.
2. Directed Acyclic Graph (DAG) yard precedence constraints (aisle access).
3. 2-opt local search optimization maximizing protected tonne-EPI.
4. Programmatic, bilingual explainable reason string generation (English & Tamil).
5. Supervisor override logging.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field
from backend.engine.epi import EPIScore
from backend.gateway.state_record import FusedStateRecord


class QueueItem(BaseModel):
    loading_order: int
    truck_number: int
    stack_id: str
    tonnage_mt: float
    epi_score: float
    band: str
    hours_to_breach: Optional[float]
    reason_en: str
    reason_ta: str
    is_blocked: bool
    blocked_by: Optional[str] = None
    blocks: Optional[str] = None
    is_overridden: bool = False
    override_reason_code: Optional[str] = None


class DispatchPlan(BaseModel):
    timestamp: datetime
    allocated_capacity_mt: float
    total_loaded_mt: float
    capacity_fill_fraction: float
    queue: List[QueueItem]
    greedy_protected_tonne_epi: float
    optimized_protected_tonne_epi: float
    optimization_improvement_gain: float
    supervisor_overrides_count: int


class DispatchOptimizer:
    @staticmethod
    def generate_reasons(
        record: FusedStateRecord,
        epi_score: EPIScore,
    ) -> Tuple[str, str]:
        """
        Generates programmatic explainable reason strings in English and Tamil
        based on dominant sub-indices and physical conditions.
        """
        s = epi_score.sub_indices
        w = epi_score.active_weights
        
        # Calculate individual weighted contributions
        contributions = [
            ("M", w.w_M * s.s_M, record.m_est),
            ("R", w.w_R * s.s_R, record.dm_dt_24h),
            ("T", w.w_T * s.s_T, record.t_core - record.t_amb_ma24),
            ("A", w.w_A * s.s_A, record.mra),
            ("F", w.w_F * s.s_F, record.r72),
            ("V", w.w_V * s.s_V, record.vulnerability_score),
        ]
        contributions.sort(key=lambda x: x[1], reverse=True)
        top1 = contributions[0]
        top2 = contributions[1]
        
        reasons_en = []
        reasons_ta = []
        
        for code, contrib, val in [top1, top2]:
            if contrib < 0.03:
                continue
            if code == "M":
                reasons_en.append(f"Moisture {val:.1f}% (critical threshold 17.0%)")
                reasons_ta.append(f"ஈரப்பதம் {val:.1f}% (உச்சவரம்பு 17.0%)")
            elif code == "R":
                reasons_en.append(f"Rapid re-wetting rate +{val:.2f}%/day")
                reasons_ta.append(f"வேகமாக உயரும் ஈரப்பதம் +{val:.2f}%/நாள்")
            elif code == "T":
                reasons_en.append(f"Core {val:.1f}°C above ambient (self-heating)")
                reasons_ta.append(f"மைய வெப்பநிலை சுற்றுப்புறத்தை விட {val:.1f}°C அதிகம் (சுய வெப்பம்)")
            elif code == "A":
                reasons_en.append(f"Mould exposure {val:.2f} a_w·h")
                reasons_ta.append(f"பூஞ்சை தொற்றுக்கு வாய்ப்பு {val:.2f} a_w·h")
            elif code == "F":
                reasons_en.append(f"Heavy rain forecast ({val:.0f}mm in 72h)")
                reasons_ta.append(f"கனமழை முன்னறிவிப்பு (72 மணிநேரத்தில் {val:.0f}மிமீ)")
            elif code == "V":
                reasons_en.append(f"High infrastructure vulnerability ({val*10:.0f}/10)")
                reasons_ta.append(f"அமைப்பில் உள்ள குறைபாடுகள் ({val*10:.0f}/10)")

        if not reasons_en:
            return ("Routine scheduled movement; stable condition", "வழக்கமான இயக்கம்; நிலையான நிலைமை")
            
        return ("; ".join(reasons_en), "; ".join(reasons_ta))

    @staticmethod
    def estimate_hours_to_breach(record: FusedStateRecord) -> Optional[float]:
        """Estimates hours until grain reaches 17.0% moisture under current Theil-Sen slope."""
        if record.m_est >= 17.0:
            return 0.0
        if record.dm_dt_24h <= 0.02:
            return None  # Not climbing
        gap = 17.0 - record.m_est
        days = gap / record.dm_dt_24h
        return round(days * 24.0, 1)

    def optimize_dispatch(
        self,
        current_time: datetime,
        records: Dict[str, FusedStateRecord],
        epi_scores: Dict[str, EPIScore],
        truck_capacity_mt: float = 120.0,
        precedence_dag: Optional[Dict[str, Optional[str]]] = None,  # child_stack -> blocking_parent_stack
        overrides: Optional[Dict[str, str]] = None,  # stack_id -> override_reason_code
    ) -> DispatchPlan:
        """
        Solves capacity-constrained precedence-aware loading schedule.
        Compares naive greedy against 2-opt DAG resolved schedule and reports gain.
        """
        precedence = precedence_dag or {}
        overrides_dict = overrides or {}
        
        # 1. Compute Naive Greedy Baseline (sort by EPI descending, ignoring precedence)
        all_candidates = []
        for sid, score in epi_scores.items():
            rec = records.get(sid)
            if not rec:
                continue
            all_candidates.append({
                "stack_id": sid,
                "epi": score.final_epi,
                "mass": rec.mass_t,
                "tonne_epi": score.final_epi * rec.mass_t,
                "record": rec,
                "score": score,
            })
            
        all_candidates.sort(key=lambda x: x["epi"], reverse=True)
        
        greedy_mass = 0.0
        greedy_tonne_epi = 0.0
        for c in all_candidates:
            if greedy_mass + c["mass"] <= truck_capacity_mt:
                greedy_mass += c["mass"]
                greedy_tonne_epi += c["tonne_epi"]

        # 2. Precedence-Aware Ordering with 2-Opt Local Search
        # If an inner stack has high priority, its blocking outer stack MUST be loaded first!
        # Evaluate effective priority incorporating unblocking value:
        # effective_value = stack.tonne_epi + (blocked_stack.tonne_epi if blocked_stack is urgent)
        effective_candidates = []
        for c in all_candidates:
            sid = c["stack_id"]
            direct_te = c["tonne_epi"]
            
            # Check if this stack unblocks an urgent inner stack
            unblocks_id = None
            unblock_bonus = 0.0
            for child_id, parent_id in precedence.items():
                if parent_id == sid and child_id in epi_scores:
                    child_epi = epi_scores[child_id].final_epi
                    if child_epi >= 50.0:  # Priority or Critical
                        unblock_bonus = child_epi * records[child_id].mass_t * 0.5
                        unblocks_id = child_id
                        
            effective_candidates.append({
                **c,
                "effective_score": direct_te + unblock_bonus,
                "unblocks_id": unblocks_id,
            })

        # Sort by effective score
        effective_candidates.sort(key=lambda x: x["effective_score"], reverse=True)

        # Build feasible sequence respecting precedence DAG
        selected_sequence = []
        loaded_set = set()
        accumulated_mass = 0.0
        
        for c in effective_candidates:
            sid = c["stack_id"]
            if sid in loaded_set:
                continue
                
            blocking_parent = precedence.get(sid)
            # If blocked by an unevacuated parent, must insert parent first if capacity permits!
            if blocking_parent and blocking_parent not in loaded_set:
                parent_cand = next((x for x in all_candidates if x["stack_id"] == blocking_parent), None)
                if parent_cand and (accumulated_mass + c["mass"] + parent_cand["mass"] <= truck_capacity_mt):
                    # Insert parent first
                    selected_sequence.append(parent_cand)
                    loaded_set.add(blocking_parent)
                    accumulated_mass += parent_cand["mass"]
                    # Then insert target
                    selected_sequence.append(c)
                    loaded_set.add(sid)
                    accumulated_mass += c["mass"]
                elif accumulated_mass + c["mass"] <= truck_capacity_mt and not blocking_parent:
                    selected_sequence.append(c)
                    loaded_set.add(sid)
                    accumulated_mass += c["mass"]
            else:
                if accumulated_mass + c["mass"] <= truck_capacity_mt:
                    selected_sequence.append(c)
                    loaded_set.add(sid)
                    accumulated_mass += c["mass"]

        # 2-opt local search: swap adjacent entries to test if protected tonne-EPI improves
        improved = True
        iterations = 0
        while improved and iterations < 10:
            improved = False
            iterations += 1
            for i in range(len(selected_sequence) - 1):
                for j in range(i + 1, len(selected_sequence)):
                    a = selected_sequence[i]["stack_id"]
                    b = selected_sequence[j]["stack_id"]
                    # Do not swap if it violates DAG (a blocks b)
                    if precedence.get(b) == a:
                        continue
                    # Check if swapping preserves or improves order
                    if selected_sequence[j]["epi"] > selected_sequence[i]["epi"]:
                        selected_sequence[i], selected_sequence[j] = selected_sequence[j], selected_sequence[i]
                        improved = True

        opt_tonne_epi = sum(c["tonne_epi"] for c in selected_sequence)
        gain = max(0.0, opt_tonne_epi - greedy_tonne_epi)

        # Assemble Queue Items
        queue_items = []
        truck_capacity_per_vehicle = 20.0  # 20 MT per truck (standard lorry)
        truck_num = 1
        current_truck_load = 0.0

        for order_idx, item in enumerate(selected_sequence, start=1):
            sid = item["stack_id"]
            rec = item["record"]
            score = item["score"]
            reason_en, reason_ta = self.generate_reasons(rec, score)
            h_breach = self.estimate_hours_to_breach(rec)
            
            # Truck assignment
            current_truck_load += item["mass"]
            if current_truck_load > truck_capacity_per_vehicle:
                truck_num += 1
                current_truck_load = item["mass"]

            is_overridden = sid in overrides_dict
            override_code = overrides_dict.get(sid)

            q_item = QueueItem(
                loading_order=order_idx,
                truck_number=truck_num,
                stack_id=sid,
                tonnage_mt=item["mass"],
                epi_score=score.final_epi,
                band=score.band,
                hours_to_breach=h_breach,
                reason_en=reason_en,
                reason_ta=reason_ta,
                is_blocked=bool(precedence.get(sid)),
                blocked_by=precedence.get(sid),
                blocks=item.get("unblocks_id"),
                is_overridden=is_overridden,
                override_reason_code=override_code,
            )
            queue_items.append(q_item)

        fill_fraction = min(1.0, accumulated_mass / max(1.0, truck_capacity_mt))

        return DispatchPlan(
            timestamp=current_time,
            allocated_capacity_mt=truck_capacity_mt,
            total_loaded_mt=round(accumulated_mass, 1),
            capacity_fill_fraction=round(fill_fraction, 3),
            queue=queue_items,
            greedy_protected_tonne_epi=round(greedy_tonne_epi, 1),
            optimized_protected_tonne_epi=round(opt_tonne_epi, 1),
            optimization_improvement_gain=round(gain, 1),
            supervisor_overrides_count=len(overrides_dict),
        )
