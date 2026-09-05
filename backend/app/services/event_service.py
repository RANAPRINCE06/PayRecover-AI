import uuid
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from collections import deque

logger = logging.getLogger("payrecover.events")


class EventService:
    """
    Real-Time Event Service managing Server-Sent Events (SSE) subscribers
    and maintaining a ring-buffer of recent operational telemetry events.
    """

    def __init__(self, max_recent: int = 50):
        self._subscribers: Set[asyncio.Queue] = set()
        self._recent_events: deque = deque(maxlen=max_recent)
        self._lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None

    def broadcast_sync(
        self,
        event_type: str,
        message: str,
        case_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        amount: Optional[float] = None,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        tool_type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronously broadcast an event (can be safely called from sync SQLAlchemy route handlers).
        Saves event to ring-buffer and pushes to all active async SSE subscriber queues.
        """
        event_payload = {
            "id": f"evt_{uuid.uuid4().hex[:10]}",
            "type": event_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "case_id": case_id,
            "payment_id": payment_id,
            "amount": amount,
            "status": status,
            "agent_type": agent_type,
            "tool_type": tool_type,
            "data": data or {},
            "correlation_id": correlation_id
        }

        # Store in recent events buffer
        self._recent_events.append(event_payload)
        logger.info(f"[RealTimeEvent] {event_type}: {message} (case: {case_id})")

        # Distribute to SSE queues
        dead_queues = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(event_payload)
            except asyncio.QueueFull:
                dead_queues.append(q)
            except Exception:
                dead_queues.append(q)

        for dq in dead_queues:
            self._subscribers.discard(dq)

        return event_payload

    async def broadcast_async(self, **kwargs) -> Dict[str, Any]:
        """Async variant of broadcast."""
        return self.broadcast_sync(**kwargs)

    async def subscribe(self) -> asyncio.Queue:
        """Register a new SSE client subscriber queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        logger.info(f"New SSE client connected. Active subscribers: {len(self._subscribers)}")
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Deregister an SSE client queue."""
        self._subscribers.discard(q)
        logger.info(f"SSE client disconnected. Active subscribers: {len(self._subscribers)}")

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve latest events in reverse chronological order."""
        events = list(self._recent_events)
        events.reverse()
        return events[:limit]


# Global singleton instance
event_service = EventService()
