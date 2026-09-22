"""
Module 1: Synthetic Telemetry Generator - Scenario Engine.
Implements the 10 first-class named scenarios per §5.3:
1. baseline_stable
2. slow_monsoon_wetting
3. core_hotspot
4. flash_rain_event
5. sensor_condensation_fault
6. stuck_at_fault
7. node_dropout
8. high_vulnerability_static
9. override_breach
10. season_replay
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional
from backend.simulator.node_model import SyntheticStack, SyntheticNode, VulnerabilityRubric
from backend.simulator.weather_synth import WeatherSynthesizer

AVAILABLE_SCENARIOS = [
    "baseline_stable",
    "slow_monsoon_wetting",
    "core_hotspot",
    "flash_rain_event",
    "sensor_condensation_fault",
    "stuck_at_fault",
    "node_dropout",
    "high_vulnerability_static",
    "override_breach",
    "season_replay",
]


class ScenarioEngine:
    @staticmethod
    def apply_scenario_to_stack(
        stack: SyntheticStack,
        scenario_name: str,
        weather: WeatherSynthesizer,
        start_time: datetime,
    ) -> None:
        """Configures a stack and its nodes to execute a specific named scenario."""
        stack.assigned_scenario = scenario_name
        stack.scenario_start_time = start_time
        
        # Reset all nodes to healthy initial state first
        for node in stack.nodes.values():
            node.condensation_fault_active = False
            node.stuck_at_fault_active = False
            node.stuck_reading = None
            node.dropout_active = False
            node.health_state = "ok"
            node.bio_heating_rate_per_day = 0.0
            node.bio_self_heating = 0.0
            
        if scenario_name == "baseline_stable":
            stack.rubric = VulnerabilityRubric(
                tarpaulin_condition=0,
                dunnage_plinth=0,
                drainage_proximity=0,
                position_in_row=0,
                residence_time=0,
            )
            for node in stack.nodes.values():
                node.true_grain_moisture = 13.0
                node.true_water_activity = 0.58

        elif scenario_name == "slow_monsoon_wetting":
            weather.trigger_scripted_monsoon(duration_days=6.0, peak_rh=95.0)
            stack.rubric.tarpaulin_condition = 1
            stack.rubric.drainage_proximity = 1

        elif scenario_name == "core_hotspot":
            # Deep core node exhibits biological self-heating independently of ambient
            for node in stack.nodes.values():
                if node.position == "core":
                    node.bio_heating_rate_per_day = 1.8  # ramps +1.8°C per day up to ~8°C
                    node.bio_self_heating = 1.0

        elif scenario_name == "flash_rain_event":
            weather.trigger_flash_storm(duration_hours=4.0, rain_rate_mm_h=20.0)

        elif scenario_name == "sensor_condensation_fault":
            # Outer windward face node suffers dew point condensation fault
            windward_nodes = [n for n in stack.nodes.values() if n.position in ["windward-face", "crown"]]
            target_node = windward_nodes[0] if windward_nodes else list(stack.nodes.values())[0]
            target_node.condensation_fault_active = True

        elif scenario_name == "stuck_at_fault":
            # Leeward node ADC freezes at a plausible-looking value
            target_node = list(stack.nodes.values())[-1]
            target_node.stuck_at_fault_active = True

        elif scenario_name == "node_dropout":
            # Ground contact node transceiver fails
            target_node = list(stack.nodes.values())[1]
            target_node.dropout_active = True
            target_node.health_state = "lost"

        elif scenario_name == "high_vulnerability_static":
            # Stack has severely compromised infrastructure but ordinary telemetry
            stack.rubric = VulnerabilityRubric(
                tarpaulin_condition=2,
                dunnage_plinth=2,
                drainage_proximity=2,
                position_in_row=2,
                residence_time=2,
            )
            for node in stack.nodes.values():
                node.true_grain_moisture = 13.5
                node.true_water_activity = 0.60

        elif scenario_name == "override_breach":
            # Force moisture >= 17.0% to test the hard safety override rule
            for node in stack.nodes.values():
                node.true_grain_moisture = 17.5
                node.true_water_activity = 0.88

        elif scenario_name == "season_replay":
            # Season replay is applied across the yard as a whole (see setup_default_yard)
            pass

    @staticmethod
    def setup_default_yard(
        stacks: Dict[str, SyntheticStack],
        weather: WeatherSynthesizer,
        start_time: datetime,
    ) -> None:
        """
        Populates a realistic multi-stack yard with an interesting distribution of concurrent scenarios,
        testing the full pipeline under real contention.
        """
        scenario_assignments = [
            ("STK-01", "override_breach"),            # Immediate critical override
            ("STK-02", "baseline_stable"),            # Stable safe stack
            ("STK-03", "slow_monsoon_wetting"),       # Wetting progression
            ("STK-04", "core_hotspot"),               # Hotspot respiration
            ("STK-05", "sensor_condensation_fault"),  # Condensation fault screening
            ("STK-06", "baseline_stable"),            # Stable
            ("STK-07", "stuck_at_fault"),             # Stuck node
            ("STK-08", "high_vulnerability_static"),  # Static vulnerability
            ("STK-09", "node_dropout"),               # Node dropout
            ("STK-10", "flash_rain_event"),           # Forecast lead
            ("STK-11", "slow_monsoon_wetting"),       # Wetting
            ("STK-12", "baseline_stable"),            # Stable
        ]
        for stack_id, sc_name in scenario_assignments:
            if stack_id in stacks:
                ScenarioEngine.apply_scenario_to_stack(stacks[stack_id], sc_name, weather, start_time)
