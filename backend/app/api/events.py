import json
import asyncio
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.event_service import event_service

logger = logging.getLogger("payrecover.api.events")
router = APIRouter(tags=["Real-Time Operations"])


@router.get("/stream")
async def stream_realtime_events(request: Request):
    """
    Server-Sent Events (SSE) endpoint providing real-time telemetry streaming
    to dashboard clients (Command Center, Live Activity Feed).
    """
    queue = await event_service.subscribe()

    async def event_generator():
        try:
            # Send initial connection confirmation event
            init_msg = json.dumps({"type": "CONNECTED", "message": "PayRecover AI real-time event stream active"})
            yield f"event: connected\ndata: {init_msg}\n\n"

            while True:
                # Disconnect if client closed connection
                if await request.is_disconnected():
                    break

                try:
                    # Wait for next event with 15-second timeout for keep-alive heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    data = json.dumps(event)
                    yield f"event: message\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive comment
                    yield ": ping\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            event_service.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/recent", response_model=List[Dict[str, Any]])
def get_recent_events(limit: int = 50):
    """
    Retrieve recently broadcast operational events to populate the dashboard activity feed on load.
    """
    return event_service.get_recent_events(limit=min(limit, 100))
