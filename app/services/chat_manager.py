from __future__ import annotations

from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)
        self.users: dict[int, str] = {}

    async def connect(self, user_id: int, username: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[user_id].add(websocket)
        self.users[user_id] = username

    def disconnect(self, user_id: int, websocket: WebSocket):
        self.connections[user_id].discard(websocket)
        if not self.connections[user_id]:
            self.connections.pop(user_id, None)
            self.users.pop(user_id, None)

    async def broadcast(self, payload: dict):
        dead: list[tuple[int, WebSocket]] = []
        for user_id, sockets in list(self.connections.items()):
            for websocket in list(sockets):
                try:
                    await websocket.send_json(payload)
                except Exception:
                    dead.append((user_id, websocket))
        for user_id, websocket in dead:
            self.disconnect(user_id, websocket)

    def online(self):
        return [
            {"id": uid, "username": name}
            for uid, name in self.users.items()
        ]


manager = ConnectionManager()
