"""Unit tests for the streaming layer (B12-B17, C10-C13).

Mocks ``Transport.request_stream`` with a canned async iterator of byte frames;
no real network. Verifies frame classification, heartbeat filtering, error
propagation, and that each service stream method targets the right path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from tradestation.errors import StreamError
from tradestation.services.brokerage import BrokerageService
from tradestation.services.market_data import MarketDataService
from tradestation.streaming import classify_frame, stream_events


class FakeTransport:
    """Records the streamed path and replays canned byte frames."""

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self.path: str | None = None
        self.params: dict[str, Any] | None = None

    async def request_stream(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> AsyncIterator[bytes]:
        self.path = path
        self.params = params

        async def _gen() -> AsyncIterator[bytes]:
            for f in self._frames:
                yield f

        return _gen()


# ---------------------------------------------------------------------------
# classify_frame
# ---------------------------------------------------------------------------


class TestClassifyFrame:
    def test_heartbeat(self) -> None:
        ev = classify_frame({"Heartbeat": 1, "Timestamp": "2026-06-01T00:00:00Z"})
        assert ev.is_heartbeat is True
        assert ev.error is None

    def test_error(self) -> None:
        ev = classify_frame({"Error": "GoAway", "Message": "too many connections"})
        assert ev.error == "too many connections"

    def test_data(self) -> None:
        ev = classify_frame({"Symbol": "AAPL", "Last": "178.45"})
        assert ev.is_heartbeat is False
        assert ev.error is None
        assert ev.raw is not None
        assert ev.raw["Symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# stream_events
# ---------------------------------------------------------------------------


class TestStreamEvents:
    async def test_filters_heartbeats_by_default(self) -> None:
        frames = [
            b'{"Symbol": "AAPL", "Last": "1"}',
            b'{"Heartbeat": 1}',
            b'{"Symbol": "AAPL", "Last": "2"}',
        ]
        transport = FakeTransport(frames)
        events = [e async for e in stream_events(transport, "/x")]  # type: ignore[arg-type]
        assert len(events) == 2
        assert all(not e.is_heartbeat for e in events)

    async def test_includes_heartbeats_when_requested(self) -> None:
        frames = [b'{"Symbol": "AAPL"}', b'{"Heartbeat": 1}']
        transport = FakeTransport(frames)
        events = [
            e
            async for e in stream_events(transport, "/x", include_heartbeats=True)  # type: ignore[arg-type]
        ]
        assert len(events) == 2
        assert events[1].is_heartbeat is True

    async def test_error_frame_raises(self) -> None:
        frames = [b'{"Symbol": "AAPL"}', b'{"Error": "Boom", "Message": "bad"}']
        transport = FakeTransport(frames)
        with pytest.raises(StreamError, match="bad"):
            _ = [e async for e in stream_events(transport, "/x")]  # type: ignore[arg-type]

    async def test_skips_malformed_lines(self) -> None:
        frames = [b"not json", b'{"Symbol": "AAPL"}', b"[1,2,3]"]
        transport = FakeTransport(frames)
        events = [e async for e in stream_events(transport, "/x")]  # type: ignore[arg-type]
        assert len(events) == 1  # only the dict frame


# ---------------------------------------------------------------------------
# Market-data stream methods (B12-B17) — path correctness
# ---------------------------------------------------------------------------


class TestMarketDataStreams:
    async def test_stream_quotes_path(self) -> None:
        transport = FakeTransport([b'{"Symbol": "AAPL"}'])
        svc = MarketDataService(transport)  # type: ignore[arg-type]
        events = [e async for e in svc.stream_quotes(["AAPL", "MSFT"])]
        assert transport.path == "/marketdata/stream/quotes/AAPL,MSFT"
        assert len(events) == 1

    async def test_stream_bars_path_and_params(self) -> None:
        transport = FakeTransport([b'{"Close": "1"}'])
        svc = MarketDataService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_bars("AAPL")]
        assert transport.path == "/marketdata/stream/barcharts/AAPL"
        assert transport.params is not None
        assert transport.params["unit"] == "Minute"

    async def test_stream_depth_quotes_path(self) -> None:
        transport = FakeTransport([])
        svc = MarketDataService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_depth_quotes("AAPL")]
        assert transport.path == "/marketdata/stream/marketdepth/quotes/AAPL"

    async def test_stream_depth_aggregates_path(self) -> None:
        transport = FakeTransport([])
        svc = MarketDataService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_depth_aggregates("AAPL")]
        assert transport.path == "/marketdata/stream/marketdepth/aggregates/AAPL"

    async def test_stream_option_chain_path(self) -> None:
        transport = FakeTransport([])
        svc = MarketDataService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_option_chain("AAPL", "2026-06-19")]
        assert transport.path == "/marketdata/stream/options/chains/AAPL"
        assert transport.params == {"expiration": "2026-06-19"}

    async def test_stream_option_quotes_path(self) -> None:
        transport = FakeTransport([])
        svc = MarketDataService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_option_quotes([{"Symbol": "AAPL 260619C200"}])]
        assert transport.path == "/marketdata/stream/options/quotes"


# ---------------------------------------------------------------------------
# Brokerage stream methods (C10-C13) — path correctness
# ---------------------------------------------------------------------------


class TestBrokerageStreams:
    async def test_stream_orders_path(self) -> None:
        transport = FakeTransport([b'{"OrderID": "1"}'])
        svc = BrokerageService(transport)  # type: ignore[arg-type]
        events = [e async for e in svc.stream_orders(["11111111"])]
        assert transport.path == "/brokerage/stream/accounts/11111111/orders"
        assert len(events) == 1

    async def test_stream_orders_by_id_path(self) -> None:
        transport = FakeTransport([])
        svc = BrokerageService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_orders_by_id(["11111111"], ["835711"])]
        assert transport.path == "/brokerage/stream/accounts/11111111/orders/835711"

    async def test_stream_positions_path(self) -> None:
        transport = FakeTransport([])
        svc = BrokerageService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_positions(["11111111", "22222222"])]
        assert transport.path == "/brokerage/stream/accounts/11111111,22222222/positions"

    async def test_stream_wallets_path(self) -> None:
        transport = FakeTransport([])
        svc = BrokerageService(transport)  # type: ignore[arg-type]
        _ = [e async for e in svc.stream_wallets(["11111111"])]
        assert transport.path == "/brokerage/stream/accounts/11111111/wallets"
