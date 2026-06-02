"""Streaming helpers — StreamEvent envelope and async-iterator utilities.

See docs/05-python-library.md §"Streaming primitives" for the full design.

TradeStation streaming endpoints return newline-delimited JSON over HTTP
chunked transfer. This module provides:

- :class:`StreamEvent` — base envelope for all stream frames.
- Helper utilities for typed async iteration (used by service methods B12-B17
  and C10-C13).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from tradestation.errors import StreamError

if TYPE_CHECKING:
    from tradestation.transport import Transport


class StreamEvent(BaseModel):
    """Envelope for a single frame received from a TradeStation stream.

    Subclassed by concrete event types (``QuoteEvent``, ``BarEvent``, etc.)
    in the service modules.  The base class carries the raw dict and two
    diagnostic flags.

    Attributes:
        raw: The original decoded JSON frame (always present).
        is_heartbeat: ``True`` when the frame is a keep-alive heartbeat.
            By default the library filters heartbeats; pass
            ``include_heartbeats=True`` to a stream method to receive them.
        error: Non-``None`` when the frame carries an error payload from the
            server.  Callers may catch :exc:`tradestation.errors.StreamError`
            instead.
    """

    raw: dict[str, Any] | None = None
    is_heartbeat: bool = False
    error: str | None = None


def classify_frame(data: dict[str, Any]) -> StreamEvent:
    """Classify a decoded stream frame into a :class:`StreamEvent`.

    TradeStation interleaves three kinds of frames into a data stream:

    - **Heartbeats**: ``{"Heartbeat": <n>, "Timestamp": "..."}`` — keep-alives.
    - **Stream status**: ``{"StreamStatus": "EndSnapshot" | ...}`` — treated as
      data frames (surfaced raw so callers can react to snapshot boundaries).
    - **Errors**: ``{"Error": "...", "Message": "..."}`` — surfaced via the
      ``error`` field (and raised by :func:`stream_events`).
    - **Data**: anything else — the actual quote / bar / order / position frame.
    """
    if "Heartbeat" in data:
        return StreamEvent(raw=data, is_heartbeat=True)
    if "Error" in data:
        msg = str(data.get("Message") or data.get("Error"))
        return StreamEvent(raw=data, error=msg)
    return StreamEvent(raw=data)


async def stream_events(
    transport: Transport,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    include_heartbeats: bool = False,
) -> AsyncIterator[StreamEvent]:
    """Open a TradeStation stream and yield typed :class:`StreamEvent` frames.

    Wraps :meth:`Transport.request_stream`, decoding each newline-delimited
    JSON frame and classifying it. Heartbeats are filtered unless
    *include_heartbeats* is set. Error frames raise :exc:`StreamError`.

    Args:
        transport: The shared transport handle.
        path: Streaming endpoint path (e.g. ``/marketdata/stream/quotes/AAPL``).
        params: Query-string parameters.
        include_heartbeats: When ``True``, also yield heartbeat events.

    Yields:
        :class:`StreamEvent` instances (data frames, optionally heartbeats).

    Raises:
        tradestation.errors.StreamError: On a server error frame or transport
            stream failure.
    """
    raw_iter = await transport.request_stream(path, params=params)
    # aclosing ensures the underlying httpx stream is closed when the consumer
    # breaks early (e.g. --max / --for), avoiding "aclose(): asynchronous
    # generator is already running" during event-loop shutdown.
    async with aclosing(cast(AsyncGenerator[bytes, None], raw_iter)) as lines:
        async for line in lines:
            try:
                data = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            event = classify_frame(data)
            if event.error is not None:
                raise StreamError(event.error, stream_url=path, payload=event.raw)
            if event.is_heartbeat and not include_heartbeats:
                continue
            yield event
