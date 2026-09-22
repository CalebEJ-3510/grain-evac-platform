"""
Module 4: WebSocket Connection Manager.
Maintains active connections to the frontend dashboard and broadcasts live updates
on every simulation tick, alert event, and override action.
"""

from __future__ import annotations
import json
from datetime import datetime
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from backend.api.schemas import WebSocketBroadcastMessage


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: WebSocketBroadcastMessage) -> None:
        payload = message.model_dump_json()
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
                
        for dead in disconnected:
            self.disconnect(dead)


ws_manager = ConnectionManager()
