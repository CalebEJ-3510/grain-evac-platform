"""
Module 1: Weather Synthesis & Open-Meteo Interface.
Provides hourly forecast scalars (R72, p_rain, RH_f), ambient ground truth,
scripted weather scenarios, and controllable feed-down fault injection.
"""

from __future__ import annotations
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel


class WeatherState(BaseModel):
    timestamp: datetime
    ambient_temp_c: float
    ambient_rh_pct: float
    is_raining: bool
    rain_rate_mm_h: float
    temp_amb_ma24: float
    
    # Forecast scalars (common to the yard)
    r72_mm: float       # 72h cumulative forecast rainfall
    p_rain: float       # Max probability of precipitation in-window (0-1)
    rh_forecast_mean: float  # Mean forecast RH (%)
    
    feed_healthy: bool = True
    feed_mode: str = "synthetic"  # "synthetic" or "live"
    is_stale: bool = False


class WeatherSynthesizer:
    def __init__(self, base_temp_c: float = 29.0, base_rh_pct: float = 68.0):
        self.base_temp = base_temp_c
        self.base_rh = base_rh_pct
        self.mode: str = "synthetic"
        self.feed_down_fault: bool = False
        
        # Scripted weather override events
        self.scripted_rain_duration_hours: float = 0.0
        self.scripted_rain_elapsed_hours: float = 0.0
        self.scripted_rain_intensity: float = 0.0
        self.scripted_rh_target: Optional[float] = None
        
        # Trailing 24h ambient temperature history for moving average
        self.temp_history: list[tuple[datetime, float]] = []
        self.last_cached_weather: Optional[WeatherState] = None

    def trigger_scripted_monsoon(self, duration_days: float = 6.0, peak_rh: float = 94.0) -> None:
        """Sets up a slow monsoon wetting event over several days."""
        self.scripted_rain_duration_hours = duration_days * 24.0
        self.scripted_rain_elapsed_hours = 0.0
        self.scripted_rain_intensity = 3.5  # light sustained monsoon rain
        self.scripted_rh_target = peak_rh

    def trigger_flash_storm(self, duration_hours: float = 4.0, rain_rate_mm_h: float = 18.0) -> None:
        """Sets up an intense flash thunderstorm with high R72 and p_rain."""
        self.scripted_rain_duration_hours = duration_hours
        self.scripted_rain_elapsed_hours = 0.0
        self.scripted_rain_intensity = rain_rate_mm_h
        self.scripted_rh_target = 95.0

    def clear_scripted_weather(self) -> None:
        self.scripted_rain_duration_hours = 0.0
        self.scripted_rain_elapsed_hours = 0.0
        self.scripted_rain_intensity = 0.0
        self.scripted_rh_target = None

    def advance(self, current_time: datetime, dt_minutes: float = 15.0) -> WeatherState:
        """Advance weather simulation by dt_minutes."""
        dt_hours = dt_minutes / 60.0
        
        # Check feed-down fault
        if self.feed_down_fault:
            if self.last_cached_weather:
                stale_state = self.last_cached_weather.model_copy()
                stale_state.feed_healthy = False
                stale_state.is_stale = True
                return stale_state
            # If no cached weather yet, return degraded fallback
            return WeatherState(
                timestamp=current_time,
                ambient_temp_c=self.base_temp,
                ambient_rh_pct=self.base_rh,
                is_raining=False,
                rain_rate_mm_h=0.0,
                temp_amb_ma24=self.base_temp,
                r72_mm=0.0,
                p_rain=0.1,
                rh_forecast_mean=self.base_rh,
                feed_healthy=False,
                feed_mode=self.mode,
                is_stale=True,
            )

        # Diurnal temperature and RH cycle
        # Hour of day (0 to 24)
        hour = current_time.hour + current_time.minute / 60.0
        # Peak temperature at ~14:00, trough at ~05:00
        diurnal_temp = 4.5 * math.sin((hour - 8.0) * math.pi / 12.0)
        # RH is inversely related to temperature in dry conditions
        diurnal_rh = -12.0 * math.sin((hour - 8.0) * math.pi / 12.0)
        
        curr_temp = self.base_temp + diurnal_temp + random.gauss(0, 0.4)
        curr_rh = self.base_rh + diurnal_rh + random.gauss(0, 1.2)
        
        is_raining = False
        rain_rate = 0.0
        r72 = 4.0 + random.uniform(0, 6.0)
        p_rain = 0.15 + random.uniform(0, 0.1)
        rh_forecast = curr_rh
        
        # Apply scripted weather
        if self.scripted_rain_duration_hours > 0 and self.scripted_rain_elapsed_hours < self.scripted_rain_duration_hours:
            self.scripted_rain_elapsed_hours += dt_hours
            progress = self.scripted_rain_elapsed_hours / self.scripted_rain_duration_hours
            
            # Monsoon or flash storm
            is_raining = True
            rain_rate = self.scripted_rain_intensity * random.uniform(0.8, 1.2)
            if self.scripted_rh_target:
                curr_rh = self.base_rh + progress * (self.scripted_rh_target - self.base_rh)
            
            # Forecast scalars lead the event
            if self.scripted_rain_intensity > 10.0:  # Flash storm
                r72 = 65.0 + random.uniform(-5.0, 5.0)
                p_rain = 0.95
                rh_forecast = 92.0
            else:  # Monsoon ramp
                r72 = min(80.0, 30.0 + progress * 50.0)
                p_rain = min(0.95, 0.60 + progress * 0.35)
                rh_forecast = min(96.0, 75.0 + progress * 20.0)
                
            curr_temp = max(23.0, curr_temp - 2.5)  # Evaporative cooling

        curr_rh = max(20.0, min(99.0, curr_rh))
        curr_temp = max(15.0, min(45.0, curr_temp))
        
        # Track 24h moving average of ambient temperature
        self.temp_history.append((current_time, curr_temp))
        cutoff_24h = current_time - timedelta(hours=24)
        self.temp_history = [(t, v) for (t, v) in self.temp_history if t >= cutoff_24h]
        temp_ma24 = sum(v for _, v in self.temp_history) / max(1, len(self.temp_history))
        
        state = WeatherState(
            timestamp=current_time,
            ambient_temp_c=round(curr_temp, 2),
            ambient_rh_pct=round(curr_rh, 1),
            is_raining=is_raining,
            rain_rate_mm_h=round(rain_rate, 2),
            temp_amb_ma24=round(temp_ma24, 2),
            r72_mm=round(r72, 1),
            p_rain=round(p_rain, 2),
            rh_forecast_mean=round(rh_forecast, 1),
            feed_healthy=True,
            feed_mode=self.mode,
            is_stale=False,
        )
        self.last_cached_weather = state
        return state
