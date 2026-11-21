"""In-memory SSE job stage broker (`/api/stream/{job_id}`) and WebSocket hub (`/ws/tilxat/{id}`)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class SSEJobBroker:
    """Stores and streams real-time pipeline stage events `{stage, state, elapsedMs}` per job_id."""

    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._done: set[str] = set()

    async def publish(self, job_id: str, event: dict[str, Any], *, done: bool = False) -> None:
        self._events[job_id].append(event)
        if done:
            self._done.add(job_id)
        for q in list(self._queues.get(job_id, [])):
            await q.put(event)

    async def subscribe(self, job_id: str, *, heartbeat_sec: float = 15.0):
        # Replay any already-emitted events first
        for ev in list(self._events.get(job_id, [])):
            yield ev
        if job_id in self._done:
            return
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues[job_id].append(q)
        elapsed_wait = 0.0
        try:
            while elapsed_wait < 45.0:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=heartbeat_sec)
                    yield ev
                    if ev.get("stage") in ("result", "done", "error") or job_id in self._done:
                        break
                except asyncio.TimeoutError:
                    elapsed_wait += heartbeat_sec
                    if job_id in self._done:
                        break
                    yield {"_heartbeat": True}
        finally:
            if q in self._queues.get(job_id, []):
                self._queues[job_id].remove(q)


class TilxatWSHub:
    """Manages live WebSocket subscribers for Tilxat two-party signing status updates."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, tilxat_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[tilxat_id].append(ws)

    def disconnect(self, tilxat_id: str, ws: WebSocket) -> None:
        if ws in self._connections.get(tilxat_id, []):
            self._connections[tilxat_id].remove(ws)

    async def broadcast(self, tilxat_id: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(tilxat_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tilxat_id, ws)


sse_broker = SSEJobBroker()
tilxat_ws_hub = TilxatWSHub()
