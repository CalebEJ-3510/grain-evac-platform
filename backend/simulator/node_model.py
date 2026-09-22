"""
Module 1: Synthetic Telemetry Generator - Node, Stack, and Yard Models.
Implements the forward physics model (sorption thermodynamics, thermal diffusion,
biological self-heating, sensor noise, and fault injection).
"""

from __future__ import annotations
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Literal, Tuple
from pydantic import BaseModel, Field

# Rough rice Chung-Pfost parameters
# Adsorption branch
A_ADS = 502.8
B_ADS = 16.5
C_ADS = 41.5

# Desorption branch
A_DES = 591.4
B_DES = 16.8
C_DES = 35.7


def forward_chung_pfost(m_wb_percent: float, temp_c: float, branch: str = "adsorption") -> float:
    """
    Computes equilibrium water activity aw (0 to 1) from moisture content (%wb) and temperature (°C).
    m_wb_percent: Grain moisture in percent wet basis (e.g. 14.2).
    temp_c: Grain temperature in °C.
    Returns: aw (decimal, 0 to 1).
    """
    # Convert %wb to dry basis decimal
    m_wb = max(0.01, min(0.40, m_wb_percent / 100.0))
    m_db = m_wb / (1.0 - m_wb)
    
    A = A_ADS if branch == "adsorption" else A_DES
    B = B_ADS if branch == "adsorption" else B_DES
    C = C_ADS if branch == "adsorption" else C_DES
    
    exponent = - (A / (temp_c + C)) * math.exp(-B * m_db)
    aw = math.exp(exponent)
    return max(0.01, min(0.999, aw))


def inverse_chung_pfost(aw: float, temp_c: float, branch: str = "adsorption") -> float:
    """
    Computes moisture content (%wb) from water activity aw (0 to 1) and temperature (°C).
    aw: Water activity (decimal, 0 to 1, equivalent to RH/100).
    temp_c: Grain temperature in °C.
    Returns: Moisture content in percent wet basis (%wb).
    """
    aw = max(0.01, min(0.999, aw))
    A = A_ADS if branch == "adsorption" else A_DES
    B = B_ADS if branch == "adsorption" else B_DES
    C = C_ADS if branch == "adsorption" else C_DES
    
    val = - (temp_c + C) * math.log(aw) / A
    if val <= 0:
        val = 1e-6
    m_db = - (1.0 / B) * math.log(val)
    # Convert dry basis decimal to wet basis percent
    m_wb = m_db / (1.0 + m_db)
    return max(1.0, min(35.0, m_wb * 100.0))


NodePosition = Literal["core", "windward-face", "leeward-face", "ground-contact", "crown"]
HealthState = Literal["ok", "degrading", "dead", "lost"]


class NodeReading(BaseModel):
    node_id: str
    stack_id: str
    timestamp: datetime
    erh_observed: float  # Percent, 0-100
    temp_observed: float  # °C
    temp_core_observed: float  # °C
    battery_voltage: float  # Volts (e.g. 3.45V)
    fault_flags: List[str] = Field(default_factory=list)


class SyntheticNode:
    def __init__(
        self,
        node_id: str,
        stack_id: str,
        position: NodePosition,
        initial_moisture_wb: float = 13.2,
        initial_temp: float = 28.0,
    ):
        self.node_id = node_id
        self.stack_id = stack_id
        self.position = position
        
        # Internal hidden true state
        self.true_grain_moisture = initial_moisture_wb
        self.true_water_activity = forward_chung_pfost(initial_moisture_wb, initial_temp, "adsorption")
        self.true_temperature = initial_temp
        self.true_core_temperature = initial_temp
        
        # Self heating biological accumulation (°C above ambient baseline)
        self.bio_self_heating = 0.0
        self.bio_heating_rate_per_day = 0.0
        
        # Branch hysteresis tracking
        self.active_branch: str = "adsorption"
        
        # Health & battery
        self.health_state: HealthState = "ok"
        self.battery_voltage_proxy = 3.60  # Initial fresh Li-SOCl2 cell
        
        # Fault injection state
        self.condensation_fault_active = False
        self.stuck_at_fault_active = False
        self.stuck_reading: Optional[Tuple[float, float, float]] = None
        self.dropout_active = False
        
        # Trailing history for dew point & stuck checks
        self.reading_history: List[Tuple[datetime, float, float]] = []

    def get_position_factors(self) -> Tuple[float, float]:
        """
        Returns (diffusion_time_constant_hours, rain_sensitivity_weight).
        Ground contact and windward face react faster under rain and reach higher peak aw.
        """
        if self.position == "ground-contact":
            return (3.0, 0.25)
        elif self.position == "windward-face":
            return (3.5, 0.20)
        elif self.position == "leeward-face":
            return (4.5, 0.10)
        elif self.position == "crown":
            return (4.0, 0.15)
        else:  # core
            return (6.5, 0.05)

    def advance_physics(
        self,
        dt_minutes: float,
        ambient_rh_pct: float,
        ambient_temp_c: float,
        is_raining: bool,
        rain_rate_mm_h: float,
        amb_temp_24h_ma: float,
    ) -> None:
        """
        Advances the node's true physical state by dt_minutes.
        """
        dt_hours = dt_minutes / 60.0
        tau_hours, rain_sensitivity = self.get_position_factors()
        
        # 1. Target equilibrium water activity
        if is_raining or rain_rate_mm_h > 0:
            # Wetting effect on perimeter and ground contact
            rain_boost = min(0.35, (rain_rate_mm_h / 15.0) * rain_sensitivity + 0.12 * rain_sensitivity)
            target_aw = min(0.95, 0.60 + rain_boost)
        else:
            # In dry weather, tarpaulins protect grain; equilibrium remains moderate
            target_aw = 0.58 + 0.05 * (ambient_rh_pct - 60.0) / 40.0 * rain_sensitivity
            target_aw = max(0.50, min(0.64, target_aw))
            
        # First-order diffusion lag toward target equilibrium
        alpha = 1.0 - math.exp(-dt_hours / tau_hours)
        prev_aw = self.true_water_activity
        self.true_water_activity = prev_aw + alpha * (target_aw - prev_aw)
        
        # Determine branch hysteresis
        if self.true_water_activity >= prev_aw:
            self.active_branch = "adsorption"
        else:
            self.active_branch = "desorption"
            
        # 2. Advance true temperatures
        # Node surface temperature tracks ambient with small lag
        t_tau = tau_hours * 0.8
        t_alpha = 1.0 - math.exp(-dt_hours / t_tau)
        self.true_temperature += t_alpha * (ambient_temp_c - self.true_temperature)
        
        # Core temperature tracks 24h ambient moving average plus biological self heating
        if self.bio_heating_rate_per_day > 0:
            self.bio_self_heating += self.bio_heating_rate_per_day * (dt_hours / 24.0)
        self.true_core_temperature = amb_temp_24h_ma + self.bio_self_heating
        
        # 3. Closed-loop true grain moisture derived via forward isotherm
        self.true_grain_moisture = inverse_chung_pfost(
            self.true_water_activity, self.true_core_temperature, self.active_branch
        )
        
        # Battery voltage monotonic decay (~0.002V per day)
        self.battery_voltage_proxy = max(2.10, self.battery_voltage_proxy - 0.002 * (dt_hours / 24.0))

    def emit_reading(self, nominal_timestamp: datetime) -> Optional[NodeReading]:
        """
        Emits an observed sensor reading with realistic Gaussian noise, jitter, and fault injection.
        Returns None if node has dropped out.
        """
        if self.dropout_active or self.health_state == "lost":
            return None
            
        # Jitter timestamp ±0 to 90 seconds
        jitter_sec = random.uniform(-90.0, 90.0)
        reading_ts = nominal_timestamp + timedelta(seconds=jitter_sec)
        
        # Check stuck-at fault
        if self.stuck_at_fault_active:
            if self.stuck_reading is None:
                self.stuck_reading = (
                    self.true_water_activity * 100.0,
                    self.true_temperature,
                    self.true_core_temperature,
                )
            return NodeReading(
                node_id=self.node_id,
                stack_id=self.stack_id,
                timestamp=reading_ts,
                erh_observed=round(self.stuck_reading[0], 2),
                temp_observed=round(self.stuck_reading[1], 2),
                temp_core_observed=round(self.stuck_reading[2], 2),
                battery_voltage=round(self.battery_voltage_proxy, 3),
                fault_flags=["stuck_at_simulated"],
            )
            
        # Check condensation fault
        if self.condensation_fault_active:
            # Pins observed RH at near 100% due to liquid dew on capacitive film
            return NodeReading(
                node_id=self.node_id,
                stack_id=self.stack_id,
                timestamp=reading_ts,
                erh_observed=round(99.8 + random.uniform(-0.2, 0.2), 2),
                temp_observed=round(self.true_temperature + random.gauss(0, 0.1), 2),
                temp_core_observed=round(self.true_core_temperature + random.gauss(0, 0.1), 2),
                battery_voltage=round(self.battery_voltage_proxy, 3),
                fault_flags=["condensation_simulated"],
            )
            
        # Standard healthy reading with sensor noise
        # ERH noise sigma ≈ 1.5%
        erh_obs = max(0.0, min(100.0, self.true_water_activity * 100.0 + random.gauss(0, 1.5)))
        # Temp noise sigma ≈ 0.3°C
        t_obs = self.true_temperature + random.gauss(0, 0.3)
        # Core temp noise sigma ≈ 0.2°C
        t_core_obs = self.true_core_temperature + random.gauss(0, 0.2)
        
        # Save to reading history
        self.reading_history.append((reading_ts, erh_obs, t_obs))
        if len(self.reading_history) > 100:
            self.reading_history.pop(0)
            
        return NodeReading(
            node_id=self.node_id,
            stack_id=self.stack_id,
            timestamp=reading_ts,
            erh_observed=round(erh_obs, 2),
            temp_observed=round(t_obs, 2),
            temp_core_observed=round(t_core_obs, 2),
            battery_voltage=round(self.battery_voltage_proxy, 3),
            fault_flags=[],
        )


class VulnerabilityRubric(BaseModel):
    tarpaulin_condition: int = Field(default=0, ge=0, le=2)  # 0: Intact, 1: Minor wear, 2: Torn/patched
    dunnage_plinth: int = Field(default=0, ge=0, le=2)        # 0: Concrete, 1: Pallets, 2: Bare ground
    drainage_proximity: int = Field(default=0, ge=0, le=2)    # 0: High ground, 1: Mild slope, 2: Depressed
    position_in_row: int = Field(default=0, ge=0, le=2)       # 0: Interior, 1: End of row, 2: Outer windward
    residence_time: int = Field(default=0, ge=0, le=2)        # 0: <30d, 1: 30-90d, 2: >90d

    @property
    def total_score(self) -> float:
        total = (
            self.tarpaulin_condition
            + self.dunnage_plinth
            + self.drainage_proximity
            + self.position_in_row
            + self.residence_time
        )
        return total / 10.0


class SyntheticStack:
    def __init__(
        self,
        stack_id: str,
        tonnage_m: float,
        row_id: str,
        position_index: int,
        formation_date: datetime,
        blocks_stack_id: Optional[str] = None,
        blocked_by_stack_id: Optional[str] = None,
        rubric: Optional[VulnerabilityRubric] = None,
    ):
        self.stack_id = stack_id
        self.tonnage_m = tonnage_m
        self.row_id = row_id
        self.position_index = position_index
        self.formation_date = formation_date
        self.blocks_stack_id = blocks_stack_id
        self.blocked_by_stack_id = blocked_by_stack_id
        self.rubric = rubric or VulnerabilityRubric()
        
        # 3 to 6 sensor nodes seeded at key depths/faces
        self.nodes: Dict[str, SyntheticNode] = {}
        self.assigned_scenario: str = "baseline_stable"
        self.scenario_start_time: Optional[datetime] = None
        
        # Ground truth tracking for evaluation (Precision@k)
        self.is_evacuated: bool = False
        self.evacuated_at: Optional[datetime] = None
        self.true_spoilage_occurred: bool = False
        self.true_spoilage_time: Optional[datetime] = None
        
        self._seed_nodes()

    def _seed_nodes(self) -> None:
        positions: List[NodePosition] = [
            "core",
            "ground-contact",
            "windward-face",
            "leeward-face",
            "crown",
        ]
        for idx, pos in enumerate(positions):
            node_id = f"{self.stack_id}-N{idx+1}"
            self.nodes[node_id] = SyntheticNode(
                node_id=node_id,
                stack_id=self.stack_id,
                position=pos,
                initial_moisture_wb=13.0 + random.uniform(-0.3, 0.4),
                initial_temp=27.5 + random.uniform(-0.5, 0.5),
            )

    def get_age_days(self, current_time: datetime) -> float:
        delta = current_time - self.formation_date
        return max(0.0, delta.total_seconds() / 86400.0)

    def advance_physics(
        self,
        dt_minutes: float,
        ambient_rh_pct: float,
        ambient_temp_c: float,
        is_raining: bool,
        rain_rate_mm_h: float,
        amb_temp_24h_ma: float,
        current_time: datetime,
    ) -> None:
        """Advance all child nodes by dt_minutes."""
        if self.is_evacuated:
            return

        for node in self.nodes.values():
            node.advance_physics(
                dt_minutes=dt_minutes,
                ambient_rh_pct=ambient_rh_pct,
                ambient_temp_c=ambient_temp_c,
                is_raining=is_raining,
                rain_rate_mm_h=rain_rate_mm_h,
                amb_temp_24h_ma=amb_temp_24h_ma,
            )
            # Check ground-truth spoilage: if true moisture >= 17.0% or true aw >= 0.85 for >24h
            if node.true_grain_moisture >= 17.0 and not self.true_spoilage_occurred:
                self.true_spoilage_occurred = True
                self.true_spoilage_time = current_time

    def emit_telemetry(self, current_time: datetime) -> List[NodeReading]:
        """Collect all readings from surviving, transmitting nodes."""
        if self.is_evacuated:
            return []
        readings = []
        for node in self.nodes.values():
            reading = node.emit_reading(current_time)
            if reading is not None:
                readings.append(reading)
        return readings
