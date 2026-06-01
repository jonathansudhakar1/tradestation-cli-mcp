"""Helper to drain a bounded number of events from an async stream.

MCP tools cannot hold a long-lived stream open across a single tool call, so
streaming endpoints are exposed as *collect* tools: open the stream, gather up
to ``max_events`` data frames (or until ``timeout_seconds`` elapses), close it,
and return the captured frames as a list of plain dicts.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any


async def collect_stream(
    stream: AsyncIterator[Any],
    *,
    max_events: int = 10,
    timeout_seconds: float = 30.0,
) -> list[dict[str, Any]]:
    """Collect up to *max_events* data frames from *stream*.

    Heartbeat events are skipped. Returns the raw frame dicts. Stops at
    whichever comes first: *max_events* data frames, *timeout_seconds*, or the
    stream ending.

    Args:
        stream: An async iterator of :class:`~tradestation.streaming.StreamEvent`.
        max_events: Maximum number of data frames to capture.
        timeout_seconds: Wall-clock cap so a quiet stream returns promptly.

    Returns:
        A list of raw frame dicts (``StreamEvent.raw``), newest last.
    """
    events: list[dict[str, Any]] = []

    async def _drain() -> None:
        async for event in stream:
            if getattr(event, "is_heartbeat", False):
                continue
            events.append(getattr(event, "raw", None) or {})
            if len(events) >= max_events:
                break

    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(_drain(), timeout=timeout_seconds)
    return events
