"""
Core WebSocket infrastructure for real-time bidirectional chat communication.

Provides:
- `WebSocketConnectionManager`: In-memory session-keyed connection registry,
  frame serialization, monotonic sequence numbering, replay ring buffer,
  and ping/pong keep-alive heartbeat.
- Event constants and frame schemas for WebSocket messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Close codes
WS_CLOSE_UNAUTHORIZED: int = 4001
WS_CLOSE_FORBIDDEN: int = 4003
WS_CLOSE_SESSION_NOT_FOUND: int = 4004
WS_CLOSE_NORMAL: int = 1000

# Buffer capacity for event replay on reconnection
MAX_REPLAY_BUFFER_SIZE: int = 200


@dataclass
class BufferedEvent:
    """An event stored in the session ring buffer for reconnection replay."""

    sequence: int
    event_type: str
    data: dict[str, Any]
    timestamp: str


@dataclass
class SessionConnection:
    """Holds active WebSocket connection and state for a single chat session."""

    websocket: WebSocket
    user_id: UUID
    project_id: UUID
    session_id: UUID
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_sequence: int = 1
    replay_buffer: deque[BufferedEvent] = field(
        default_factory=lambda: deque(maxlen=MAX_REPLAY_BUFFER_SIZE)
    )
    last_ping_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class WebSocketConnectionManager:
    """Thread-safe manager for active WebSocket connections across chat sessions."""

    def __init__(self) -> None:
        self._connections: dict[UUID, SessionConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        project_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> SessionConnection:
        """Register and accept a new WebSocket connection for a session.

        If a connection for this session_id already exists, the old one is closed.
        """
        await websocket.accept()

        async with self._lock:
            existing = self._connections.get(session_id)
            if existing is not None:
                try:
                    await existing.websocket.close(
                        code=WS_CLOSE_NORMAL,
                        reason="Replaced by new connection",
                    )
                except Exception as exc:
                    logger.debug(
                        "Error closing previous websocket for session %s: %s",
                        session_id,
                        exc,
                    )

            conn = SessionConnection(
                websocket=websocket,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
            )
            self._connections[session_id] = conn
            logger.info(
                "WebSocket connected: session_id=%s, user_id=%s, project_id=%s",
                session_id,
                user_id,
                project_id,
            )
            return conn

    async def disconnect(self, session_id: UUID) -> None:
        """Unregister a WebSocket connection upon disconnect."""
        async with self._lock:
            conn = self._connections.pop(session_id, None)
            if conn is not None:
                logger.info("WebSocket disconnected: session_id=%s", session_id)

    def get_connection(self, session_id: UUID) -> SessionConnection | None:
        """Retrieve the active connection for a session, if any."""
        return self._connections.get(session_id)

    async def send_event(
        self,
        session_id: UUID,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> int | None:
        """Send a structured event frame to a session's WebSocket client.

        Frames are assigned a monotonically increasing sequence number and
        buffered for replay on reconnect.

        Returns:
            The sequence number of the sent frame, or None if no connection exists.
        """
        conn = self.get_connection(session_id)
        if conn is None:
            return None

        event_data = data or {}
        now_iso = datetime.now(tz=UTC).isoformat()

        async with conn.lock:
            seq = conn.next_sequence
            conn.next_sequence += 1

            frame = {
                "type": event_type,
                "sequence": seq,
                "data": event_data,
                "timestamp": now_iso,
            }

            buffered = BufferedEvent(
                sequence=seq,
                event_type=event_type,
                data=event_data,
                timestamp=now_iso,
            )
            conn.replay_buffer.append(buffered)

            try:
                await conn.websocket.send_text(json.dumps(frame, default=str))
                return seq
            except Exception as exc:
                logger.warning(
                    "Failed to send event %s (seq=%d) to session %s: %s",
                    event_type,
                    seq,
                    session_id,
                    exc,
                )
                return None

    async def replay_events_since(
        self,
        session_id: UUID,
        last_sequence: int,
    ) -> bool:
        """Replay buffered events with sequence > last_sequence to the client.

        Returns:
            True if replay was fulfilled, False if requested sequence is too old
            (i.e., evicted from buffer, necessitating full resync).
        """
        conn = self.get_connection(session_id)
        if conn is None:
            return False

        async with conn.lock:
            if not conn.replay_buffer:
                return True

            oldest_seq = conn.replay_buffer[0].sequence
            if last_sequence < oldest_seq - 1:
                # Sequence has been evicted, notify client to do full HTTP resync
                await conn.websocket.send_text(
                    json.dumps(
                        {
                            "type": "resync_required",
                            "data": {
                                "oldest_available_sequence": oldest_seq,
                                "requested_sequence": last_sequence,
                            },
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    )
                )
                return False

            for item in conn.replay_buffer:
                if item.sequence > last_sequence:
                    frame = {
                        "type": item.event_type,
                        "sequence": item.sequence,
                        "data": item.data,
                        "timestamp": item.timestamp,
                        "replayed": True,
                    }
                    await conn.websocket.send_text(json.dumps(frame, default=str))

            return True

    async def broadcast_ping(self) -> None:
        """Heartbeat: send ping frames to all active connections."""
        now = datetime.now(tz=UTC)
        for session_id, conn in list(self._connections.items()):
            try:
                await self.send_event(session_id, "ping", {"timestamp": now.isoformat()})
                conn.last_ping_at = now
            except Exception as exc:
                logger.debug("Failed ping to session %s: %s", session_id, exc)


# Global singleton instance
websocket_manager = WebSocketConnectionManager()
