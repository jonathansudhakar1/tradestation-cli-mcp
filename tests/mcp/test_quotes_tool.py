"""Tests for the ``market_data_get_quotes`` MCP tool (B2) against a fake client.

Verifies structured response shape when the tool is wired to a real
MarketDataService stub that returns Quote model instances.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tradestation.models.market_data import Quote

# ---------------------------------------------------------------------------
# Fake quote data
# ---------------------------------------------------------------------------

_QUOTE_AAPL = Quote.model_validate(
    {
        "Symbol": "AAPL",
        "Last": "178.45",
        "Bid": "178.44",
        "BidSize": "400",
        "Ask": "178.46",
        "AskSize": "300",
        "NetChange": "1.27",
        "NetChangePct": "0.72",
        "Volume": "42113800",
        "TradeTime": "2026-06-01T16:30:00Z",
        "MarketFlags": {"IsHalted": False},
    }
)

_QUOTE_ES = Quote.model_validate(
    {
        "Symbol": "ES.M26",
        "Last": "5318.50",
        "Bid": "5318.25",
        "Ask": "5318.75",
        "NetChange": "18.50",
        "NetChangePct": "0.35",
        "Volume": "125000",
        "TradeTime": "2026-06-01T16:30:00Z",
        "MarketFlags": {"IsHalted": False},
    }
)

_QUOTE_BTC = Quote.model_validate(
    {
        "Symbol": "BTCUSD",
        "Last": "71235.78",
        "Bid": "0",
        "Ask": "0",
        "NetChange": "-2340.728",
        "NetChangePct": "-3.18",
        "Volume": "691",
        "TradeTime": "2026-06-01T16:30:00Z",
        "MarketFlags": {"IsHalted": False},
    }
)

_ALL_QUOTES = [_QUOTE_AAPL, _QUOTE_ES, _QUOTE_BTC]


# ---------------------------------------------------------------------------
# Fake client returning Quote models
# ---------------------------------------------------------------------------


class FakeMarketDataWithQuoteModels:
    """Fake service that returns Quote model instances (not raw dicts)."""

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        return [q for q in _ALL_QUOTES if q.symbol in symbols] or _ALL_QUOTES

    async def get_bars(self, symbol: str, **kwargs: Any) -> list[dict]:
        return []

    async def get_symbols(self, symbols: list[str]) -> list[dict]:
        return []

    async def list_symbol_lists(self) -> list[dict]:
        return []

    async def get_symbol_list(self, list_id: str) -> dict:
        return {}

    async def get_symbol_list_symbols(self, list_id: str) -> list[dict]:
        return []

    async def list_crypto_pairs(self) -> list[dict]:
        return [{"Name": "BTCUSD"}, {"Name": "ETHUSD"}]

    async def get_option_expirations(self, underlying: str, **kwargs: Any) -> list[dict]:
        return []

    async def get_option_strikes(self, underlying: str, **kwargs: Any) -> list[dict]:
        return []

    async def list_option_spread_types(self) -> list[dict]:
        return []

    async def option_risk_reward(self, legs: list[dict], *, entry: float) -> dict:
        return {}

    async def stream_bars(self, symbol: str, **kwargs: Any) -> list[dict]:
        return []

    async def stream_quotes(self, symbols: list[str]) -> list[dict]:
        return []

    async def stream_depth_quotes(self, symbol: str) -> list[dict]:
        return []

    async def stream_depth_aggregates(self, symbol: str) -> list[dict]:
        return []

    async def stream_option_chain(self, underlying: str, expiration: str) -> list[dict]:
        return []

    async def stream_option_quotes(self, legs: list[dict]) -> list[dict]:
        return []


class FakeClientWithQuoteModels:
    def __init__(self) -> None:
        self.market_data = FakeMarketDataWithQuoteModels()
        from tests.mcp.conftest import FakeBrokerageService, FakeOrderExecutionService

        self.brokerage = FakeBrokerageService()
        self.order_execution = FakeOrderExecutionService()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _get_data(result: Any) -> Any:
    if result.data is not None:
        return result.data
    if result.content:
        return json.loads(result.content[0].text)
    return None


class TestMarketDataGetQuotesTool:
    @pytest.mark.asyncio
    async def test_get_quotes_aapl_returns_quote_data(self) -> None:
        """market_data_get_quotes returns structured quote for AAPL."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        fake = FakeClientWithQuoteModels()
        srv = build_server(toolsets="market", client=fake)
        async with Client(srv) as c:
            result = await c.call_tool("market_data_get_quotes", {"symbols": ["AAPL"]})

        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_get_quotes_multi_symbol(self) -> None:
        """market_data_get_quotes works with multiple symbols."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        fake = FakeClientWithQuoteModels()
        srv = build_server(toolsets="market", client=fake)
        async with Client(srv) as c:
            result = await c.call_tool(
                "market_data_get_quotes",
                {"symbols": ["AAPL", "ES.M26", "BTCUSD"]},
            )

        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_get_quotes_futures_symbol(self) -> None:
        """market_data_get_quotes handles futures symbols (ES.M26)."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        fake = FakeClientWithQuoteModels()
        srv = build_server(toolsets="market", client=fake)
        async with Client(srv) as c:
            result = await c.call_tool("market_data_get_quotes", {"symbols": ["ES.M26"]})

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_get_quotes_crypto_symbol(self) -> None:
        """market_data_get_quotes handles crypto symbols (BTCUSD)."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        fake = FakeClientWithQuoteModels()
        srv = build_server(toolsets="market", client=fake)
        async with Client(srv) as c:
            result = await c.call_tool("market_data_get_quotes", {"symbols": ["BTCUSD"]})

        assert result.is_error is False
