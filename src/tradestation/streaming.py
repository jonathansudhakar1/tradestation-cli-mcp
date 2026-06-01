"""Streaming helpers — StreamEvent envelope and async-iterator utilities.

See docs/05-python-library.md §"Streaming primitives" for the full design.

TradeStation streaming endpoints return newline-delimited JSON over HTTP
chunked transfer. This module provides:

- :class:`StreamEvent` — base envelope for all stream frames.
- Helper utilities for typed async iteration (used by service methods B12-B17
  and C10-C13).

Implementation: Phase 2.
"""

from __future__ import annotations

from pydantic import BaseModel


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

    raw: dict[str, object] | None = None
    is_heartbeat: bool = False
    error: str | None = None
