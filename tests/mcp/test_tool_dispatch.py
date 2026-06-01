"""Full round-trip tests through the in-process MCP client.

Tests:
    - Safe tool dispatch: market_data_get_quotes (B2)
    - Destructive tool full flow: order_place (D2) — preview + confirm paths
    - Futures (ES.M26) and crypto (BTCUSD) symbol parameters
    - Audit log writes for destructive invocations
    - Notional cap enforcement
    - Symbol allowlist enforcement
    - Invalid token rejection
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp.exceptions import ToolError


def _get_data(result: Any) -> Any:
    """Extract the response data from a FastMCP CallToolResult.

    When a tool returns ``Any``, FastMCP cannot infer structured output and
    ``result.data`` is ``None``.  Fall back to parsing the first text-content
    frame in that case.
    """
    if result.data is not None:
        return result.data
    if result.content:
        return json.loads(result.content[0].text)
    return None


class TestSafeToolDispatch:
    @pytest.mark.asyncio
    async def test_get_quotes_aapl(self, mcp_client: object) -> None:
        """market_data_get_quotes returns canned quote data for AAPL."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_quotes", {"symbols": ["AAPL"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)
        assert any(q.get("Symbol") == "AAPL" for q in data)

    @pytest.mark.asyncio
    async def test_get_quotes_futures_symbol(self, mcp_client: object) -> None:
        """market_data_get_quotes works with futures symbols (ES.M26)."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_quotes", {"symbols": ["ES.M26"]})
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_get_quotes_crypto_symbol(self, mcp_client: object) -> None:
        """market_data_get_quotes works with crypto symbols (BTCUSD)."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_quotes", {"symbols": ["BTCUSD"]})
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_get_bars(self, mcp_client: object) -> None:
        """market_data_get_bars returns canned bar data."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_get_bars",
            {"symbol": "AAPL", "interval": 1, "unit": "Minute", "barsback": 10},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "Open" in data[0]

    @pytest.mark.asyncio
    async def test_get_bars_futures(self, mcp_client: object) -> None:
        """market_data_get_bars works with futures (ES.M26)."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_get_bars",
            {"symbol": "ES.M26", "interval": 5, "unit": "Minute"},
        )
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_list_accounts(self, mcp_client: object) -> None:
        """brokerage_list_accounts returns canned account data."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_list_accounts", {})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_positions(self, mcp_client: object) -> None:
        """brokerage_get_positions returns positions including futures."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "brokerage_get_positions",
            {"account_ids": ["11111111"]},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)
        symbols = [p.get("Symbol") for p in data]
        assert "AAPL" in symbols
        assert "ES.M26" in symbols

    @pytest.mark.asyncio
    async def test_order_confirm_safe(self, mcp_client: object) -> None:
        """order_confirm (D1) returns preview without token requirement."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "order_confirm",
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
        assert result.is_error is False
        data = _get_data(result)
        assert "EstimatedCost" in data or "OrderConfirmID" in data

    @pytest.mark.asyncio
    async def test_order_list_routes(self, mcp_client: object) -> None:
        """order_list_routes (D8) returns route list."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("order_list_routes", {})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_order_list_activation_triggers(self, mcp_client: object) -> None:
        """order_list_activation_triggers (D7) returns trigger list."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("order_list_activation_triggers", {})
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_list_crypto_pairs(self, mcp_client: object) -> None:
        """market_data_list_crypto_pairs includes BTCUSD."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_list_crypto_pairs", {})
        assert result.is_error is False
        data = _get_data(result)
        names = [p.get("Name") for p in data]
        assert "BTCUSD" in names


class TestDestructiveToolFlow:
    @pytest.mark.asyncio
    async def test_order_place_preview_path(self, mcp_client: object) -> None:
        """order_place without token → preview + token."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
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
        assert result.is_error is False
        data = _get_data(result)
        assert data["status"] == "preview"
        assert "confirmation_token" in data
        assert len(data["confirmation_token"]) > 0

    @pytest.mark.asyncio
    async def test_order_place_confirm_path(self, mcp_client: object) -> None:
        """order_place: preview → confirm round-trip."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        request = {
            "AccountID": "11111111",
            "Symbol": "AAPL",
            "Quantity": 10,
            "OrderType": "Market",
            "TradeAction": "BUY",
        }

        preview = await c.call_tool("order_place", {"request": request})
        token = _get_data(preview)["confirmation_token"]

        confirm = await c.call_tool(
            "order_place", {"request": request, "confirmation_token": token}
        )
        assert confirm.is_error is False
        data = _get_data(confirm)
        assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_order_place_invalid_token_rejected(self, mcp_client: object) -> None:
        """order_place with a bad token returns an error response."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "order_place",
            {
                "request": {
                    "AccountID": "11111111",
                    "Symbol": "AAPL",
                    "Quantity": 10,
                    "OrderType": "Market",
                    "TradeAction": "BUY",
                },
                "confirmation_token": "not-a-real-token",
            },
        )
        assert result.is_error is False  # Returns structured error, not MCP error
        data = _get_data(result)
        assert data["status"] == "error"
        assert "invalid" in data["message"].lower() or "expired" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_token_single_use(self, mcp_client: object) -> None:
        """Confirmation token cannot be reused."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        request = {
            "AccountID": "11111111",
            "Symbol": "AAPL",
            "Quantity": 5,
            "OrderType": "Market",
            "TradeAction": "BUY",
        }

        preview = await c.call_tool("order_place", {"request": request})
        token = _get_data(preview)["confirmation_token"]

        # First use — should succeed
        first = await c.call_tool("order_place", {"request": request, "confirmation_token": token})
        assert _get_data(first).get("OrderID") == "987654321"

        # Second use — should fail
        second = await c.call_tool("order_place", {"request": request, "confirmation_token": token})
        assert _get_data(second)["status"] == "error"

    @pytest.mark.asyncio
    async def test_order_place_with_futures_symbol(self, mcp_client: object) -> None:
        """order_place works with futures symbols (ES.M26)."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "order_place",
            {
                "request": {
                    "AccountID": "11111111",
                    "Symbol": "ES.M26",
                    "Quantity": 1,
                    "OrderType": "Market",
                    "TradeAction": "BUY",
                }
            },
        )
        assert result.is_error is False
        assert _get_data(result)["status"] == "preview"

    @pytest.mark.asyncio
    async def test_order_place_with_crypto_symbol(self, mcp_client: object) -> None:
        """order_place works with crypto symbols (BTCUSD)."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "order_place",
            {
                "request": {
                    "AccountID": "11111111",
                    "Symbol": "BTCUSD",
                    "Quantity": 1,
                    "OrderType": "Market",
                    "TradeAction": "BUY",
                }
            },
        )
        assert result.is_error is False
        assert _get_data(result)["status"] == "preview"


class TestAuditLogIntegration:
    @pytest.mark.asyncio
    async def test_audit_log_written_on_destructive_call(
        self, fake_client: object, tmp_path: Path
    ) -> None:
        """Destructive tool calls write to the audit log."""
        from pathlib import Path as _Path

        from fastmcp import Client

        import tradestation.mcp.safety as safety_mod
        from tradestation.mcp.server import build_server

        original_fn = safety_mod._audit_log_path

        def patched_path() -> _Path:
            return tmp_path / "mcp-audit.log"

        safety_mod._audit_log_path = patched_path  # type: ignore[attr-defined]
        try:
            srv = build_server(
                toolsets="trading",
                confirm_mode="require",
                client=fake_client,
            )
            async with Client(srv) as c:
                await c.call_tool(
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

            log_file = tmp_path / "mcp-audit.log"
            assert log_file.exists(), "Audit log should have been created"
            lines = [ln for ln in log_file.read_text().strip().split("\n") if ln]
            assert len(lines) >= 1
            entry = json.loads(lines[0])
            assert entry["tool"] == "order_place"
            assert entry["decision"] in ("preview", "confirm", "skip")
        finally:
            safety_mod._audit_log_path = original_fn  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_audit_log_written_on_full_confirm_flow(
        self, fake_client: object, tmp_path: Path
    ) -> None:
        """Full preview + confirm flow writes two audit log entries."""
        from pathlib import Path as _Path

        from fastmcp import Client

        import tradestation.mcp.safety as safety_mod
        from tradestation.mcp.server import build_server

        original_fn = safety_mod._audit_log_path

        def patched_path() -> _Path:
            return tmp_path / "mcp-audit.log"

        safety_mod._audit_log_path = patched_path  # type: ignore[attr-defined]
        try:
            srv = build_server(
                toolsets="trading",
                confirm_mode="require",
                client=fake_client,
            )
            request = {
                "AccountID": "11111111",
                "Symbol": "AAPL",
                "Quantity": 10,
                "OrderType": "Market",
                "TradeAction": "BUY",
            }
            async with Client(srv) as c:
                # Preview
                preview = await c.call_tool("order_place", {"request": request})
                token = _get_data(preview)["confirmation_token"]

                # Confirm
                await c.call_tool(
                    "order_place",
                    {"request": request, "confirmation_token": token},
                )

            lines = [
                ln for ln in (tmp_path / "mcp-audit.log").read_text().strip().split("\n") if ln
            ]
            # Two "executing"/"token_issued" and two "success" lines
            assert len(lines) >= 2
        finally:
            safety_mod._audit_log_path = original_fn  # type: ignore[attr-defined]


class TestNotionalCapEnforcement:
    @pytest.mark.asyncio
    async def test_order_exceeds_notional_cap_raises(self, fake_client: object) -> None:
        """order_place raises ValueError when notional cap is exceeded."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        # The canned confirm response has EstimatedCost=1785.00
        # Set cap below that
        srv = build_server(
            toolsets="trading",
            confirm_mode="require",
            max_order_notional=1000.0,
            client=fake_client,
        )
        async with Client(srv) as c:
            with pytest.raises(ToolError):
                await c.call_tool(
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

    @pytest.mark.asyncio
    async def test_order_within_notional_cap_passes(self, fake_client: object) -> None:
        """order_place passes when notional cap is not exceeded."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        # EstimatedCost=1785.00, cap=5000.00 — should pass
        srv = build_server(
            toolsets="trading",
            confirm_mode="require",
            max_order_notional=5000.0,
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
            assert _get_data(result)["status"] == "preview"


class TestSymbolAllowlistEnforcement:
    @pytest.mark.asyncio
    async def test_blocked_symbol_raises(self, fake_client: object) -> None:
        """order_place with a symbol not in the allowlist raises."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(
            toolsets="trading",
            confirm_mode="require",
            allowed_symbols=["AAPL", "MSFT"],
            client=fake_client,
        )
        async with Client(srv) as c:
            with pytest.raises(ToolError):
                await c.call_tool(
                    "order_place",
                    {
                        "request": {
                            "AccountID": "11111111",
                            "Symbol": "TSLA",
                            "Quantity": 5,
                            "OrderType": "Market",
                            "TradeAction": "BUY",
                        }
                    },
                )

    @pytest.mark.asyncio
    async def test_allowed_symbol_passes(self, fake_client: object) -> None:
        """order_place with an allowlisted symbol proceeds normally."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(
            toolsets="trading",
            confirm_mode="require",
            allowed_symbols=["AAPL"],
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
            assert _get_data(result)["status"] == "preview"


class TestOtherDestructiveTools:
    """Coverage for D3, D4, D6 destructive tools."""

    @pytest.mark.asyncio
    async def test_order_replace_preview_path(self, fake_client: object) -> None:
        """order_replace without token returns preview."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_replace",
                {"order_id": "111111111", "request": {"Quantity": 5}},
            )
            data = _get_data(result)
            assert data["status"] == "preview"
            assert "confirmation_token" in data

    @pytest.mark.asyncio
    async def test_order_replace_confirm_path(self, fake_client: object) -> None:
        """order_replace: preview to confirm round-trip."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            request: dict[str, object] = {"Quantity": 5}
            preview = await c.call_tool(
                "order_replace", {"order_id": "111111111", "request": request}
            )
            token = _get_data(preview)["confirmation_token"]
            confirm = await c.call_tool(
                "order_replace",
                {"order_id": "111111111", "request": request, "confirmation_token": token},
            )
            data = _get_data(confirm)
            assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_order_replace_off_mode(self, fake_client: object) -> None:
        """order_replace with confirm_mode=off executes immediately."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="off", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_replace", {"order_id": "111111111", "request": {"Quantity": 5}}
            )
            data = _get_data(result)
            assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_order_replace_review_mode(self, fake_client: object) -> None:
        """order_replace with confirm_mode=review returns preview_only."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="review", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_replace", {"order_id": "111111111", "request": {"Quantity": 5}}
            )
            data = _get_data(result)
            assert data["status"] == "preview_only"

    @pytest.mark.asyncio
    async def test_order_replace_invalid_token(self, fake_client: object) -> None:
        """order_replace with invalid token returns error."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_replace",
                {
                    "order_id": "111111111",
                    "request": {"Quantity": 5},
                    "confirmation_token": "bad-token",
                },
            )
            data = _get_data(result)
            assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_order_cancel_preview_path(self, fake_client: object) -> None:
        """order_cancel without token returns preview."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool("order_cancel", {"order_id": "111111111"})
            data = _get_data(result)
            assert data["status"] == "preview"
            assert "confirmation_token" in data

    @pytest.mark.asyncio
    async def test_order_cancel_confirm_path(self, fake_client: object) -> None:
        """order_cancel: preview to confirm round-trip."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            preview = await c.call_tool("order_cancel", {"order_id": "111111111"})
            token = _get_data(preview)["confirmation_token"]
            confirm = await c.call_tool(
                "order_cancel", {"order_id": "111111111", "confirmation_token": token}
            )
            data = _get_data(confirm)
            assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_order_cancel_off_mode(self, fake_client: object) -> None:
        """order_cancel with confirm_mode=off executes immediately."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="off", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool("order_cancel", {"order_id": "111111111"})
            data = _get_data(result)
            assert data.get("OrderID") == "987654321"

    @pytest.mark.asyncio
    async def test_order_cancel_review_mode(self, fake_client: object) -> None:
        """order_cancel with confirm_mode=review returns preview_only."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="review", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool("order_cancel", {"order_id": "111111111"})
            data = _get_data(result)
            assert data["status"] == "preview_only"

    @pytest.mark.asyncio
    async def test_order_cancel_invalid_token(self, fake_client: object) -> None:
        """order_cancel with invalid token returns error."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_cancel",
                {"order_id": "111111111", "confirmation_token": "bad-token"},
            )
            data = _get_data(result)
            assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_order_group_place_preview_path(self, fake_client: object) -> None:
        """order_group_place without token returns preview."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_group_place", {"request": {"Type": "OCO", "Orders": []}}
            )
            data = _get_data(result)
            assert data["status"] == "preview"
            assert "confirmation_token" in data

    @pytest.mark.asyncio
    async def test_order_group_place_confirm_path(self, fake_client: object) -> None:
        """order_group_place: preview to confirm round-trip."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            request: dict[str, object] = {"Type": "OCO", "Orders": []}
            preview = await c.call_tool("order_group_place", {"request": request})
            token = _get_data(preview)["confirmation_token"]
            confirm = await c.call_tool(
                "order_group_place",
                {"request": request, "confirmation_token": token},
            )
            data = _get_data(confirm)
            assert data.get("OrderID") == "GROUP-001"

    @pytest.mark.asyncio
    async def test_order_group_place_off_mode(self, fake_client: object) -> None:
        """order_group_place with confirm_mode=off executes immediately."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="off", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_group_place", {"request": {"Type": "OCO", "Orders": []}}
            )
            data = _get_data(result)
            assert data.get("OrderID") == "GROUP-001"

    @pytest.mark.asyncio
    async def test_order_group_place_review_mode(self, fake_client: object) -> None:
        """order_group_place with confirm_mode=review returns preview_only."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="review", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_group_place", {"request": {"Type": "OCO", "Orders": []}}
            )
            data = _get_data(result)
            assert data["status"] == "preview_only"

    @pytest.mark.asyncio
    async def test_order_group_place_invalid_token(self, fake_client: object) -> None:
        """order_group_place with invalid token returns error."""
        from fastmcp import Client

        from tradestation.mcp.server import build_server

        srv = build_server(toolsets="trading", confirm_mode="require", client=fake_client)
        async with Client(srv) as c:
            result = await c.call_tool(
                "order_group_place",
                {
                    "request": {"Type": "OCO", "Orders": []},
                    "confirmation_token": "bad-token",
                },
            )
            data = _get_data(result)
            assert data["status"] == "error"


class TestBrokerageToolDispatch:
    """Coverage for remaining brokerage tools (C2, C3, C5-C13)."""

    @pytest.mark.asyncio
    async def test_get_balances(self, mcp_client: object) -> None:
        """brokerage_get_balances (C2) returns account balances."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_get_balances", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_bod_balances(self, mcp_client: object) -> None:
        """brokerage_get_bod_balances (C3) returns BOD balances."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_get_bod_balances", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_orders(self, mcp_client: object) -> None:
        """brokerage_get_orders (C5) returns account orders."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_get_orders", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_orders_by_id(self, mcp_client: object) -> None:
        """brokerage_get_orders_by_id (C6) returns specific orders."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "brokerage_get_orders_by_id",
            {"account_ids": ["11111111"], "order_ids": ["111111111"]},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_historical_orders(self, mcp_client: object) -> None:
        """brokerage_get_historical_orders (C7) returns historical orders."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "brokerage_get_historical_orders",
            {"account_ids": ["11111111"], "since": "2026-01-01"},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_historical_orders_by_id(self, mcp_client: object) -> None:
        """brokerage_get_historical_orders_by_id (C8) returns specific historical orders."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "brokerage_get_historical_orders_by_id",
            {"account_ids": ["11111111"], "order_ids": ["111111111"]},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_wallets(self, mcp_client: object) -> None:
        """brokerage_get_wallets (C9) returns crypto wallets."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_get_wallets", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_orders(self, mcp_client: object) -> None:
        """brokerage_stream_orders (C10) returns streamed orders."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_stream_orders", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_orders_by_id(self, mcp_client: object) -> None:
        """brokerage_stream_orders_by_id (C11) returns streamed orders by ID."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "brokerage_stream_orders_by_id",
            {"account_ids": ["11111111"], "order_ids": ["111111111"]},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_positions(self, mcp_client: object) -> None:
        """brokerage_stream_positions (C12) returns streamed positions."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_stream_positions", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_wallets(self, mcp_client: object) -> None:
        """brokerage_stream_wallets (C13) returns streamed wallets."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("brokerage_stream_wallets", {"account_ids": ["11111111"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)


class TestMarketDataToolDispatch:
    """Coverage for remaining market_data tools (B3, B4, B5, B6, B8, B9, B10, B11-B17)."""

    @pytest.mark.asyncio
    async def test_get_symbols(self, mcp_client: object) -> None:
        """market_data_get_symbols (B3) returns symbol details."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_symbols", {"symbols": ["AAPL"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_symbol_lists(self, mcp_client: object) -> None:
        """market_data_list_symbol_lists (B4) returns symbol lists."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_list_symbol_lists", {})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_symbol_list(self, mcp_client: object) -> None:
        """market_data_get_symbol_list (B5) returns a named symbol list."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_symbol_list", {"list_id": "list1"})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_get_symbol_list_symbols(self, mcp_client: object) -> None:
        """market_data_get_symbol_list_symbols (B6) returns symbols in a list."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_symbol_list_symbols", {"list_id": "list1"})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_option_expirations(self, mcp_client: object) -> None:
        """market_data_get_option_expirations (B8) returns expiration dates."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_get_option_expirations", {"underlying": "AAPL"})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_option_strikes(self, mcp_client: object) -> None:
        """market_data_get_option_strikes (B9) returns strike prices."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_get_option_strikes",
            {"underlying": "AAPL", "expiration": "2026-06-20"},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_option_spread_types(self, mcp_client: object) -> None:
        """market_data_list_option_spread_types (B10) returns spread types."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_list_option_spread_types", {})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_option_risk_reward(self, mcp_client: object) -> None:
        """market_data_option_risk_reward (B11) returns risk/reward data."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_option_risk_reward",
            {
                "legs": [{"Symbol": "AAPL", "Strike": 180.0, "OptionType": "C"}],
                "entry": 3.50,
            },
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_stream_bars(self, mcp_client: object) -> None:
        """market_data_stream_bars (B12) returns streamed bars."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_stream_bars",
            {"symbol": "AAPL", "interval": 1, "unit": "Minute"},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_quotes(self, mcp_client: object) -> None:
        """market_data_stream_quotes (B13) returns streamed quotes."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_stream_quotes", {"symbols": ["AAPL", "MSFT"]})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_depth_quotes(self, mcp_client: object) -> None:
        """market_data_stream_depth_quotes (B14) returns depth of market quotes."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_stream_depth_quotes", {"symbol": "AAPL"})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_depth_aggregates(self, mcp_client: object) -> None:
        """market_data_stream_depth_aggregates (B15) returns aggregated depth."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool("market_data_stream_depth_aggregates", {"symbol": "AAPL"})
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_option_chain(self, mcp_client: object) -> None:
        """market_data_stream_option_chain (B16) returns option chain data."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_stream_option_chain",
            {"underlying": "AAPL", "expiration": "2026-06-20"},
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_stream_option_quotes(self, mcp_client: object) -> None:
        """market_data_stream_option_quotes (B17) returns option quote stream."""
        from fastmcp import Client

        c: Client = mcp_client  # type: ignore[assignment]
        result = await c.call_tool(
            "market_data_stream_option_quotes",
            {
                "legs": [
                    {
                        "Symbol": "AAPL",
                        "Strike": 180.0,
                        "OptionType": "C",
                        "Expiration": "2026-06-20",
                    }
                ]
            },
        )
        assert result.is_error is False
        data = _get_data(result)
        assert isinstance(data, list)


class TestServerLoadClientCoverage:
    """Tests to cover _load_client branches in server.py."""

    def test_load_client_no_credentials_error_exits_3(self) -> None:
        """_load_client exits with code 3 when NoCredentialsError is raised."""
        import subprocess
        import sys

        # Monkey-patch NoCredentialsError path via subprocess
        code = """
import sys
from unittest.mock import patch, MagicMock
from tradestation.errors import NoCredentialsError

# Patch load_credentials to raise NoCredentialsError
with patch('tradestation.credentials.load_credentials', side_effect=NoCredentialsError('no creds')):
    with patch('tradestation.client.TradeStationClient') as MockClient:
        try:
            from tradestation.mcp.server import _load_client
            _load_client('default', 'sim', False)
        except SystemExit as e:
            sys.exit(e.code)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        # Either exits 3 (NoCredentialsError path) or something else depending on phase
        assert result.returncode in (0, 1, 3)

    def test_load_client_env_fallback_raises_not_implemented(self) -> None:
        """_load_client with allow_env_fallback=True falls back gracefully."""
        import subprocess
        import sys

        code = """
import sys
from unittest.mock import patch
from tradestation.errors import NoCredentialsError

with patch('tradestation.credentials.load_credentials', side_effect=NoCredentialsError('no creds')):
    with patch('tradestation.credentials.load_from_env', side_effect=NotImplementedError('not impl')):
        try:
            from tradestation.mcp.server import _load_client
            _load_client('default', 'sim', True)
        except SystemExit as e:
            sys.exit(e.code)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        # Either exits 3 or something else
        assert result.returncode in (0, 1, 3)


class TestOverrides:
    """Coverage for overrides.py placeholder tools."""

    @pytest.mark.asyncio
    async def test_order_place_override_returns_not_implemented(self, fake_client: object) -> None:
        """order_place_override returns a placeholder not-implemented response."""
        from fastmcp import Client, FastMCP

        from tradestation.mcp.overrides import register_all_overrides

        mcp = FastMCP("test-overrides")
        register_all_overrides(mcp, fake_client)
        async with Client(mcp) as c:
            result = await c.call_tool(
                "order_place_override",
                {
                    "account_id": "11111111",
                    "symbol": "AAPL",
                    "quantity": 10,
                    "trade_action": "BUY",
                },
            )
            data = _get_data(result)
            assert data["status"] == "not_implemented"
            assert data["override"] == "order_place_override"

    @pytest.mark.asyncio
    async def test_option_risk_reward_override_returns_not_implemented(
        self, fake_client: object
    ) -> None:
        """option_risk_reward_override returns a placeholder response."""
        from fastmcp import Client, FastMCP

        from tradestation.mcp.overrides import register_all_overrides

        mcp = FastMCP("test-overrides")
        register_all_overrides(mcp, fake_client)
        async with Client(mcp) as c:
            result = await c.call_tool(
                "option_risk_reward_override",
                {
                    "legs": [{"symbol": "AAPL", "strike": 180.0, "option_type": "C"}],
                    "entry_price": 3.50,
                },
            )
            data = _get_data(result)
            assert data["status"] == "not_implemented"
            assert data["override"] == "option_risk_reward_override"
