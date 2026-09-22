"""
Module 2: Weather Client (Open-Meteo REST Client & Offline Caching).
Fetches real Open-Meteo weather if enabled, or seamlessly falls back to the synthetic synthesizer.
Maintains cached forecast if the network/API drops, flagging staleness gracefully.
"""

from __future__ import annotations
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from backend.simulator.weather_synth import WeatherState, WeatherSynthesizer


class WeatherGatewayClient:
    def __init__(
        self,
        synthesizer: WeatherSynthesizer,
        latitude: float = 10.7870,  # Thanjavur, Tamil Nadu
        longitude: float = 79.1378,
    ):
        self.synthesizer = synthesizer
        self.latitude = latitude
        self.longitude = longitude
        self.live_enabled: bool = False
        self.last_cached_weather: Optional[WeatherState] = None

    def set_live_mode(self, enabled: bool) -> None:
        self.live_enabled = enabled
        self.synthesizer.mode = "live" if enabled else "synthetic"

    async def fetch_weather(self, current_time: datetime, dt_minutes: float = 15.0) -> WeatherState:
        """
        Fetches the current weather state.
        If live mode is enabled, attempts Open-Meteo API. If API fails or times out,
        gracefully falls back to last cached forecast with is_stale=True, or synthesizer.
        """
        if not self.live_enabled:
            weather = self.synthesizer.advance(current_time, dt_minutes)
            self.last_cached_weather = weather
            return weather

        # Attempt Open-Meteo API query
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.latitude}&longitude={self.longitude}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation"
            f"&hourly=precipitation,relative_humidity_2m"
            f"&forecast_days=3"
        )
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    curr = data.get("current", {})
                    hourly = data.get("hourly", {})
                    
                    temp_2m = curr.get("temperature_2m", 29.0)
                    rh_2m = curr.get("relative_humidity_2m", 70.0)
                    precip = curr.get("precipitation", 0.0)
                    
                    # 72h precipitation sum
                    hourly_precip = hourly.get("precipitation", [])
                    r72 = sum(hourly_precip[:72]) if hourly_precip else 5.0
                    
                    # p_rain approximation
                    rain_hours = sum(1 for p in hourly_precip[:72] if p > 0.1)
                    p_rain = min(0.99, rain_hours / 36.0) if hourly_precip else 0.2
                    
                    hourly_rh = hourly.get("relative_humidity_2m", [])
                    rh_f_mean = (sum(hourly_rh[:72]) / len(hourly_rh[:72])) if hourly_rh else rh_2m
                    
                    state = WeatherState(
                        timestamp=current_time,
                        ambient_temp_c=round(temp_2m, 2),
                        ambient_rh_pct=round(rh_2m, 1),
                        is_raining=precip > 0.0,
                        rain_rate_mm_h=round(precip, 2),
                        temp_amb_ma24=round(temp_2m - 1.0, 2),  # approximation
                        r72_mm=round(r72, 1),
                        p_rain=round(p_rain, 2),
                        rh_forecast_mean=round(rh_f_mean, 1),
                        feed_healthy=True,
                        feed_mode="live",
                        is_stale=False,
                    )
                    self.last_cached_weather = state
                    return state
        except Exception as e:
            # Fallback to cached or synthetic with stale flag
            if self.last_cached_weather:
                stale = self.last_cached_weather.model_copy()
                stale.is_stale = True
                stale.feed_healthy = False
                return stale
                
        # Final fallback to synthesizer
        synth_weather = self.synthesizer.advance(current_time, dt_minutes)
        synth_weather.is_stale = True
        return synth_weather
