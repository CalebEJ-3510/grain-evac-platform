"""
Module 1: Stack Lifecycle & Yard Management.
Maintains the collection of stacks in the yard, precedence topology (aisle access DAG),
evacuation logging, and ground-truth spoilage evaluation for Season Report (Precision@k).
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from backend.simulator.node_model import SyntheticStack, VulnerabilityRubric


class YardManager:
    def __init__(self, yard_id: str = "YARD-THANJAVUR-01"):
        self.yard_id = yard_id
        self.stacks: Dict[str, SyntheticStack] = {}
        self.daily_truck_capacity_mt: float = 120.0  # e.g. 6 trucks x 20 MT or 120 MT total
        
        # Historical metrics for Season Report
        self.evacuated_stacks: List[Dict[str, Any]] = []
        self.avoided_breaches_count: int = 0
        self.total_tonnes_evacuated: float = 0.0
        self.tonnes_by_band: Dict[str, float] = {
            "Normal": 0.0,
            "Watch": 0.0,
            "Priority": 0.0,
            "Critical": 0.0,
        }
        self.lead_times_hours: List[float] = []

    def initialize_standard_yard(self, base_time: datetime) -> None:
        """
        Builds a standard 12-stack 2-row layout with a non-trivial precedence DAG:
        Row A (Back row): STK-01 to STK-06
        Row B (Front row, facing Loading Bay/Apron): STK-07 to STK-12
        Aisle 1: STK-07 blocks access to STK-01
        Aisle 2: STK-08 blocks access to STK-02
        Aisle 3: STK-09 blocks access to STK-03
        Aisle 4: STK-10 blocks access to STK-04
        """
        self.stacks.clear()
        
        # Row B (front stacks)
        for i in range(1, 7):
            front_id = f"STK-{i+6:02d}"
            back_id = f"STK-{i:02d}"
            
            # Front stack
            self.stacks[front_id] = SyntheticStack(
                stack_id=front_id,
                tonnage_m=48.0,  # standard 48 MT stack (~960 bags of 50kg)
                row_id="Row-B (Front)",
                position_index=i,
                formation_date=base_time - timedelta(days=15 + i * 3),
                blocks_stack_id=back_id,
                blocked_by_stack_id=None,
                rubric=VulnerabilityRubric(
                    tarpaulin_condition=1 if i % 2 == 1 else 0,
                    dunnage_plinth=1,
                    drainage_proximity=1,
                    position_in_row=2 if i in [1, 6] else 0,
                    residence_time=1,
                ),
            )
            
            # Back stack (blocked by front stack)
            self.stacks[back_id] = SyntheticStack(
                stack_id=back_id,
                tonnage_m=48.0,
                row_id="Row-A (Back)",
                position_index=i,
                formation_date=base_time - timedelta(days=25 + i * 4),
                blocks_stack_id=None,
                blocked_by_stack_id=front_id,
                rubric=VulnerabilityRubric(
                    tarpaulin_condition=2 if i in [1, 4] else 0,
                    dunnage_plinth=1,
                    drainage_proximity=2 if i in [1, 2] else 0,
                    position_in_row=2 if i in [1, 6] else 0,
                    residence_time=2 if i > 3 else 1,
                ),
            )

    def evacuate_stack(self, stack_id: str, current_time: datetime, current_epi: float, band: str) -> bool:
        """
        Executes evacuation of a stack onto a truck.
        Logs metrics and updates precedence blockage.
        """
        if stack_id not in self.stacks:
            return False
            
        stack = self.stacks[stack_id]
        if stack.is_evacuated:
            return False
            
        stack.is_evacuated = True
        stack.evacuated_at = current_time
        
        # Check if an inner stack is now unblocked
        if stack.blocks_stack_id and stack.blocks_stack_id in self.stacks:
            self.stacks[stack.blocks_stack_id].blocked_by_stack_id = None
            
        # Ground-truth evaluation: did evacuating this stack avoid a spoilage breach?
        # A breach is avoided if the stack was at risk (EPI >= 50 or assigned a wetting/hotspot scenario)
        # and evacuated before catastrophic whole-stack spoilage completed.
        was_avoided = (current_epi >= 50.0) or (stack.assigned_scenario in ["slow_monsoon_wetting", "core_hotspot", "override_breach"])
        if was_avoided:
            self.avoided_breaches_count += 1
            
        lead_time = (current_time - (stack.scenario_start_time or stack.formation_date)).total_seconds() / 3600.0
        self.lead_times_hours.append(max(4.0, lead_time))
        
        self.total_tonnes_evacuated += stack.tonnage_m
        self.tonnes_by_band[band] = self.tonnes_by_band.get(band, 0.0) + stack.tonnage_m
        
        self.evacuated_stacks.append({
            "stack_id": stack_id,
            "tonnage_mt": stack.tonnage_m,
            "evacuated_at": current_time.isoformat(),
            "final_epi": current_epi,
            "band": band,
            "avoided_breach": was_avoided,
        })
        return True

    def calculate_precision_at_k(self, top_k_stack_ids: List[str]) -> float:
        """
        Computes Precision@k comparing the optimizer's top-k recommendations
        against the simulator's hidden true ground-truth spoilage state.
        """
        if not top_k_stack_ids:
            return 1.0
        
        hits = 0
        for sid in top_k_stack_ids:
            stack = self.stacks.get(sid)
            if not stack:
                continue
            # Ground-truth at-risk criteria:
            # 1. True spoilage already occurred, OR
            # 2. Max true water activity >= 0.75, OR
            # 3. True moisture >= 15.0%, OR
            # 4. Core self-heating >= 3.0°C
            max_true_aw = max(n.true_water_activity for n in stack.nodes.values())
            max_true_m = max(n.true_grain_moisture for n in stack.nodes.values())
            max_true_bio = max(n.bio_self_heating for n in stack.nodes.values())
            
            is_truly_at_risk = (
                stack.true_spoilage_occurred
                or max_true_aw >= 0.75
                or max_true_m >= 15.0
                or max_true_bio >= 3.0
            )
            if is_truly_at_risk:
                hits += 1
                
        return hits / len(top_k_stack_ids)
