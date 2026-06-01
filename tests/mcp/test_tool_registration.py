"""Assert that every inventory row has a registered MCP tool.

This is the drift-detection guarantee: if a new row is added to the inventory
and the tool is not registered, this test fails.

Inventory IDs covered:
    B1-B17  (17 market-data tools)
    C1-C13  (13 brokerage tools)
    D1-D8   ( 8 order-execution tools)
    Total: 38 inventory-ID tools
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Mapping: inventory ID -> expected MCP tool name
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES: list[tuple[str, str]] = [
    # B-series (market data)
    ("B1", "market_data_get_bars"),
    ("B2", "market_data_get_quotes"),
    ("B3", "market_data_get_symbols"),
    ("B4", "market_data_list_symbol_lists"),
    ("B5", "market_data_get_symbol_list"),
    ("B6", "market_data_get_symbol_list_symbols"),
    ("B7", "market_data_list_crypto_pairs"),
    ("B8", "market_data_get_option_expirations"),
    ("B9", "market_data_get_option_strikes"),
    ("B10", "market_data_list_option_spread_types"),
    ("B11", "market_data_option_risk_reward"),
    ("B12", "market_data_stream_bars"),
    ("B13", "market_data_stream_quotes"),
    ("B14", "market_data_stream_depth_quotes"),
    ("B15", "market_data_stream_depth_aggregates"),
    ("B16", "market_data_stream_option_chain"),
    ("B17", "market_data_stream_option_quotes"),
    # C-series (brokerage)
    ("C1", "brokerage_list_accounts"),
    ("C2", "brokerage_get_balances"),
    ("C3", "brokerage_get_bod_balances"),
    ("C4", "brokerage_get_positions"),
    ("C5", "brokerage_get_orders"),
    ("C6", "brokerage_get_orders_by_id"),
    ("C7", "brokerage_get_historical_orders"),
    ("C8", "brokerage_get_historical_orders_by_id"),
    ("C9", "brokerage_get_wallets"),
    ("C10", "brokerage_stream_orders"),
    ("C11", "brokerage_stream_orders_by_id"),
    ("C12", "brokerage_stream_positions"),
    ("C13", "brokerage_stream_wallets"),
    # D-series (order execution)
    ("D1", "order_confirm"),
    ("D2", "order_place"),
    ("D3", "order_replace"),
    ("D4", "order_cancel"),
    ("D5", "order_group_confirm"),
    ("D6", "order_group_place"),
    ("D7", "order_list_activation_triggers"),
    ("D8", "order_list_routes"),
]

TOTAL_EXPECTED = len(EXPECTED_TOOL_NAMES)  # Should be 38


def _get_registered_tool_names(mcp_server: Any) -> set[str]:
    """Synchronously retrieve the set of tool names from a FastMCP server."""

    async def _inner() -> set[str]:
        tools = await mcp_server.list_tools()
        return {t.name for t in tools}

    return asyncio.run(_inner())


class TestToolCount:
    def test_total_expected_is_38(self) -> None:
        """Sanity-check: our expected list has exactly 38 entries."""
        assert TOTAL_EXPECTED == 38, (
            f"Expected 38 inventory tools, but EXPECTED_TOOL_NAMES has {TOTAL_EXPECTED}. "
            "Update the list to match the inventory."
        )

    def test_all_38_tools_registered(self, mcp_server: Any) -> None:
        """Every B/C/D-series inventory ID has a registered tool."""
        registered = _get_registered_tool_names(mcp_server)
        missing = []
        for op_id, tool_name in EXPECTED_TOOL_NAMES:
            if tool_name not in registered:
                missing.append(f"{op_id} → {tool_name}")

        assert not missing, (
            f"{len(missing)} tool(s) missing from MCP server:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_registered_count_is_at_least_38(self, mcp_server: Any) -> None:
        """The server has at least 38 inventory tools registered."""
        registered = _get_registered_tool_names(mcp_server)
        # auth_status is an extra tool beyond the 38 inventory IDs
        # overrides may add more
        inventory_names = {name for _, name in EXPECTED_TOOL_NAMES}
        registered_inventory = registered & inventory_names
        assert len(registered_inventory) == 38, (
            f"Expected 38 inventory tools, found {len(registered_inventory)}.\n"
            f"Missing: {inventory_names - registered}"
        )


class TestIndividualTools:
    """Parametrized test: each inventory ID has its tool registered."""

    @pytest.mark.parametrize("op_id,tool_name", EXPECTED_TOOL_NAMES)
    def test_tool_registered(
        self, op_id: str, tool_name: str, mcp_server: Any
    ) -> None:
        """Tool {tool_name} (inventory {op_id}) is registered."""
        registered = _get_registered_tool_names(mcp_server)
        assert tool_name in registered, (
            f"Inventory {op_id} tool '{tool_name}' is not registered on the MCP server."
        )
