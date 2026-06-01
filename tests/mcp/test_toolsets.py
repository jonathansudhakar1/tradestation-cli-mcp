"""Tests for toolset allowlist, --read-only, and --confirm-trades behavior."""

from __future__ import annotations

import json
from typing import Any

import pytest


def _get_data(result: Any) -> Any:
    """Extract data from FastMCP CallToolResult (handles Any return types)."""
    if result.data is not None:
        return result.data
    if result.content:
        return json.loads(result.content[0].text)
    return None


def _tool_names(mcp_server: object) -> set[str]:
    """Synchronously get tool names from a FastMCP server."""
    import asyncio

    async def _get():  # type: ignore[return]
        return await mcp_server.list_tools()  # type: ignore[attr-defined]

    tools = asyncio.run(_get())
    return {t.name for t in tools}


class TestToolsetFiltering:
    def test_all_toolsets_registered_by_default(self) -> None:
        """Default 'all' toolsets registers market + brokerage + trading + auth."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="all", client=FakeTradeStationClient())
        names = _tool_names(srv)

        # Spot-check one from each series
        assert "market_data_get_quotes" in names
        assert "brokerage_list_accounts" in names
        assert "order_place" in names
        assert "auth_status" in names

    def test_market_only_disables_brokerage(self) -> None:
        """--toolsets market disables brokerage and trading tools."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="market", client=FakeTradeStationClient())
        names = _tool_names(srv)

        assert "market_data_get_quotes" in names
        assert "brokerage_list_accounts" not in names
        assert "order_place" not in names

    def test_brokerage_only_disables_market(self) -> None:
        """--toolsets brokerage disables market and trading tools."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="brokerage", client=FakeTradeStationClient())
        names = _tool_names(srv)

        assert "brokerage_list_accounts" in names
        assert "market_data_get_quotes" not in names
        assert "order_place" not in names

    def test_market_and_brokerage_no_trading(self) -> None:
        """--toolsets market,brokerage disables trading but keeps both data toolsets."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="market,brokerage", client=FakeTradeStationClient())
        names = _tool_names(srv)

        assert "market_data_get_quotes" in names
        assert "brokerage_list_accounts" in names
        assert "order_place" not in names

    def test_auth_only(self) -> None:
        """--toolsets auth includes only auth_status."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="auth", client=FakeTradeStationClient())
        names = _tool_names(srv)

        assert "auth_status" in names
        assert "market_data_get_quotes" not in names
        assert "brokerage_list_accounts" not in names
        assert "order_place" not in names


class TestReadOnly:
    def test_read_only_removes_d_series(self) -> None:
        """--read-only removes all D-series tools."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server
        from tradestation.mcp.toolsets import TRADING_TOOLS

        srv = build_server(toolsets="all", read_only=True, client=FakeTradeStationClient())
        names = _tool_names(srv)

        for tool in TRADING_TOOLS:
            assert tool not in names, f"Expected {tool} to be absent in read-only mode"

    def test_read_only_keeps_market_and_brokerage(self) -> None:
        """--read-only still includes market and brokerage tools."""
        from tests.mcp.conftest import FakeTradeStationClient
        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="all", read_only=True, client=FakeTradeStationClient())
        names = _tool_names(srv)

        assert "market_data_get_quotes" in names
        assert "brokerage_list_accounts" in names


class TestConfirmTradesMode:
    @pytest.mark.asyncio
    async def test_confirm_trades_require_returns_preview_first(
        self,
        mcp_client: object,
    ) -> None:
        """With confirm-trades=require, order_place without token returns preview."""
        from fastmcp import Client as FastMCPClient

        c: FastMCPClient = mcp_client  # type: ignore[assignment]

        result = await c.call_tool(
            "order_place",
            {
                "request": {
                    "AccountID": "11111111",
                    "Symbol": "AAPL",
                    "Quantity": 10,
                    "OrderType": "Market",
                    "TradeAction": "BUY",
                }
            },
        )
        data = _get_data(result)
        assert data["status"] == "preview"
        assert "confirmation_token" in data
        assert data["preview"] is not None

    @pytest.mark.asyncio
    async def test_confirm_trades_require_confirm_path(
        self,
        mcp_client: object,
    ) -> None:
        """confirm-trades=require: round-trip preview → confirm."""
        from fastmcp import Client as FastMCPClient

        c: FastMCPClient = mcp_client  # type: ignore[assignment]

        request = {
            "AccountID": "11111111",
            "Symbol": "AAPL",
            "Quantity": 10,
            "OrderType": "Market",
            "TradeAction": "BUY",
        }

        # First call — get preview + token
        preview_result = await c.call_tool("order_place", {"request": request})
        token = _get_data(preview_result)["confirmation_token"]

        # Second call — submit with token
        confirm_result = await c.call_tool(
            "order_place",
            {"request": request, "confirmation_token": token},
        )
        data = _get_data(confirm_result)
        assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_confirm_trades_off_executes_immediately(
        self,
        fake_client: object,
    ) -> None:
        """With confirm-trades=off, order_place executes without a token."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(
            toolsets="trading",
            confirm_mode="off",
            client=fake_client,
        )
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_place",
                {
                    "request": {
                        "AccountID": "11111111",
                        "Symbol": "AAPL",
                        "Quantity": 10,
                        "OrderType": "Market",
                        "TradeAction": "BUY",
                    }
                },
            )
            data = _get_data(result)
            assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_confirm_trades_review_returns_preview_only(
        self,
        fake_client: object,
    ) -> None:
        """With confirm-trades=review, order_place returns preview only."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(
            toolsets="trading",
            confirm_mode="review",
            client=fake_client,
        )
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_place",
                {
                    "request": {
                        "AccountID": "11111111",
                        "Symbol": "AAPL",
                        "Quantity": 10,
                        "OrderType": "Market",
                        "TradeAction": "BUY",
                    }
                },
            )
            data = _get_data(result)
            assert data["status"] == "preview_only"
            assert "confirmation_token" not in data
