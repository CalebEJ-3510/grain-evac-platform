"""
Module 1: Simulation Clock Engine.
Maintains a decoupled simulation clock that advances in configurable
wall-time per simulated 15-minute tick, driving both generator and gateway.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable, Optional, List


class SimulationClock:
    def __init__(
        self,
        start_time: Optional[datetime] = None,
        tick_interval_sim_minutes: float = 15.0,
        wall_seconds_per_tick: float = 1.0,  # default: 1 second wall time per 15-min sim tick (900x real-time)
    ):
        self.sim_time: datetime = start_time or datetime(2026, 9, 15, 6, 0, 0, tzinfo=timezone.utc)
        self.start_sim_time: datetime = self.sim_time
        self.tick_interval_sim_minutes = tick_interval_sim_minutes
        self.wall_seconds_per_tick = wall_seconds_per_tick
        
        self.is_running: bool = False
        self.speed_multiplier: float = 900.0  # 900x: 1s wall time = 15 min sim
        self._callbacks: List[Callable[[datetime, float], Awaitable[None]]] = []
        self._task: Optional[asyncio.Task] = None

    def register_tick_callback(self, cb: Callable[[datetime, float], Awaitable[None]]) -> None:
        self._callbacks.append(cb)

    def set_speed(self, multiplier: float) -> None:
        """
        multiplier: e.g.
        1.0 (real-time: 15 min wall time per tick)
        60.0 (15 sec wall time per tick)
        900.0 (1 sec wall time per tick)
        1800.0 (0.5 sec wall time per tick)
        """
        self.speed_multiplier = max(1.0, multiplier)
        # wall_seconds_per_tick = (15 * 60) / speed_multiplier
        self.wall_seconds_per_tick = (self.tick_interval_sim_minutes * 60.0) / self.speed_multiplier

    async def step(self) -> datetime:
        """Manually advances the clock by exactly one 15-minute tick."""
        self.sim_time += timedelta(minutes=self.tick_interval_sim_minutes)
        for cb in self._callbacks:
            try:
                await cb(self.sim_time, self.tick_interval_sim_minutes)
            except Exception as e:
                print(f"[SimulationClock] Error in tick callback: {e}")
        return self.sim_time

    async def _run_loop(self) -> None:
        while self.is_running:
            await self.step()
            # Sleep for the configured wall time per tick
            await asyncio.sleep(self.wall_seconds_per_tick)

    def play(self) -> None:
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._run_loop())

    def pause(self) -> None:
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    def reset(self, start_time: Optional[datetime] = None) -> None:
        self.pause()
        self.sim_time = start_time or self.start_sim_time
