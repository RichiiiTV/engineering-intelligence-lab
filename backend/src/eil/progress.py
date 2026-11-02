"""Content-free progress projection over existing durable investigation events."""

import asyncio
import json

from .auth import COOKIE, AuthenticationError, AuthStore
from .runs import STOPPED

MAX_CURSOR = 2**53 - 1  # Exact integer in both SQLite and browser JavaScript.
REPLAY_LIMIT = 100
AUTH_CHECK_SECONDS = 1
STAGES = {
    "queued": "queued",
    "running": "preparing",
    "resume_requested": "queued",
    "model_started": "generating",
    "tool_started": "retrieving",
    "model_finished": "checking",
    "pause_requested": "stopping",
    "cancel_requested": "stopping",
}


def project(event_id, kind):
    """Use only trusted event type enums; never inspect event payload contents."""
    if kind in STOPPED:
        return {
            "id": event_id,
            "stage": "completed" if kind == "completed" else "stopped",
            "status": kind,
        }
    if kind in STAGES:
        return {"id": event_id, "stage": STAGES[kind]}
    return None


def recent_events(store, run_id, cursor):
    with store.connection() as conn:
        return conn.execute(
            "SELECT id,type FROM events WHERE run_id=? AND id>? ORDER BY id DESC LIMIT ?",
            (run_id, cursor, REPLAY_LIMIT),
        ).fetchall()[::-1]


def wire(value):
    return f"id: {value['id']}\nevent: progress\ndata: {json.dumps(value)}\n\n"


async def stream_progress(store, run_id, request, cursor):
    idle = 0
    next_auth = 0
    emitted_terminal = None
    while not await request.is_disconnected():
        current = asyncio.get_running_loop().time()
        if current >= next_auth:
            try:
                await asyncio.to_thread(
                    AuthStore(store.directory).authenticate, request.cookies.get(COOKIE)
                )
            except AuthenticationError:
                return
            next_auth = current + AUTH_CHECK_SECONDS
        batch = recent_events(store, run_id, cursor)
        for event_id, kind in batch:
            cursor = max(cursor, event_id)
            value = project(cursor, kind)
            if value is not None:
                emitted_terminal = value.get("status")
                yield wire(value)
        status = store.get(run_id)["status"]
        if status in STOPPED:
            if emitted_terminal != status:
                yield wire(project(cursor, status))
            return
        if batch:
            idle = 0
            continue
        idle += 1
        if idle % 100 == 0:
            yield ": heartbeat\n\n"
        await asyncio.sleep(0.1)
