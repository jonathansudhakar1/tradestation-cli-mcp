"""Brokerage MCP tools (C-series).

Each ``register_*`` function registers one MCP tool on the given FastMCP
server.  Handlers delegate to ``client.brokerage.<method>`` and return the
result.

Inventory coverage: C1-C13 (13 tools).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from tradestation.mcp._collect import collect_stream

# ---------------------------------------------------------------------------
# C1 — GET /brokerage/accounts
# ---------------------------------------------------------------------------


def register_brokerage_list_accounts(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_list_accounts`` tool (C1)."""

    @mcp.tool(name="brokerage_list_accounts")
    async def brokerage_list_accounts() -> Any:
        """List all brokerage accounts for the authenticated user (C1)."""
        return await client.brokerage.list_accounts()

    brokerage_list_accounts._ts_op_id = "C1"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C2 — GET /brokerage/accounts/{accountIDs}/balances
# ---------------------------------------------------------------------------


def register_brokerage_get_balances(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_balances`` tool (C2)."""

    @mcp.tool(name="brokerage_get_balances")
    async def brokerage_get_balances(
        account_ids: list[str],
    ) -> Any:
        """Fetch real-time balances for one or more accounts (C2).

        Args:
            account_ids: List of account IDs.
        """
        return await client.brokerage.get_balances(account_ids)

    brokerage_get_balances._ts_op_id = "C2"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C3 — GET /brokerage/accounts/{accountIDs}/balances/bod
# ---------------------------------------------------------------------------


def register_brokerage_get_bod_balances(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_bod_balances`` tool (C3)."""

    @mcp.tool(name="brokerage_get_bod_balances")
    async def brokerage_get_bod_balances(
        account_ids: list[str],
    ) -> Any:
        """Fetch beginning-of-day balances for one or more accounts (C3).

        Args:
            account_ids: List of account IDs.
        """
        return await client.brokerage.get_bod_balances(account_ids)

    brokerage_get_bod_balances._ts_op_id = "C3"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C4 — GET /brokerage/accounts/{accountIDs}/positions
# ---------------------------------------------------------------------------


def register_brokerage_get_positions(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_positions`` tool (C4)."""

    @mcp.tool(name="brokerage_get_positions")
    async def brokerage_get_positions(
        account_ids: list[str],
    ) -> Any:
        """Fetch open positions for one or more accounts (C4).

        Args:
            account_ids: List of account IDs.
        """
        return await client.brokerage.get_positions(account_ids)

    brokerage_get_positions._ts_op_id = "C4"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C5 — GET /brokerage/accounts/{accountIDs}/orders
# ---------------------------------------------------------------------------


def register_brokerage_get_orders(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_orders`` tool (C5)."""

    @mcp.tool(name="brokerage_get_orders")
    async def brokerage_get_orders(
        account_ids: list[str],
    ) -> Any:
        """Fetch today's orders for one or more accounts (C5).

        Args:
            account_ids: List of account IDs.
        """
        return await client.brokerage.get_orders(account_ids)

    brokerage_get_orders._ts_op_id = "C5"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C6 — GET /brokerage/accounts/{accountIDs}/orders/{orderIDs}
# ---------------------------------------------------------------------------


def register_brokerage_get_orders_by_id(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_orders_by_id`` tool (C6)."""

    @mcp.tool(name="brokerage_get_orders_by_id")
    async def brokerage_get_orders_by_id(
        account_ids: list[str],
        order_ids: list[str],
    ) -> Any:
        """Fetch specific orders by order ID (C6).

        Args:
            account_ids: List of account IDs.
            order_ids: List of order IDs.
        """
        return await client.brokerage.get_orders_by_id(account_ids, order_ids)

    brokerage_get_orders_by_id._ts_op_id = "C6"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C7 — GET /brokerage/accounts/{accountIDs}/historicalorders
# ---------------------------------------------------------------------------


def register_brokerage_get_historical_orders(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_historical_orders`` tool (C7)."""

    @mcp.tool(name="brokerage_get_historical_orders")
    async def brokerage_get_historical_orders(
        account_ids: list[str],
        since: str,
    ) -> Any:
        """Fetch historical orders since a given date (C7).

        Args:
            account_ids: List of account IDs.
            since: Start date (inclusive) as ISO-8601 date string (YYYY-MM-DD).
        """
        from datetime import date

        since_date = date.fromisoformat(since)
        return await client.brokerage.get_historical_orders(account_ids, since_date)

    brokerage_get_historical_orders._ts_op_id = "C7"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C8 — GET /brokerage/accounts/{accountIDs}/historicalorders/{orderIDs}
# ---------------------------------------------------------------------------


def register_brokerage_get_historical_orders_by_id(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_historical_orders_by_id`` tool (C8)."""

    @mcp.tool(name="brokerage_get_historical_orders_by_id")
    async def brokerage_get_historical_orders_by_id(
        account_ids: list[str],
        order_ids: list[str],
    ) -> Any:
        """Fetch specific historical orders by order ID (C8).

        Args:
            account_ids: List of account IDs.
            order_ids: List of order IDs.
        """
        return await client.brokerage.get_historical_orders_by_id(account_ids, order_ids)

    brokerage_get_historical_orders_by_id._ts_op_id = "C8"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C9 — GET /brokerage/accounts/{accountIDs}/wallets
# ---------------------------------------------------------------------------


def register_brokerage_get_wallets(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_get_wallets`` tool (C9)."""

    @mcp.tool(name="brokerage_get_wallets")
    async def brokerage_get_wallets(
        account_ids: list[str],
    ) -> Any:
        """Fetch crypto wallets for one or more accounts (C9).

        Args:
            account_ids: List of account IDs.
        """
        return await client.brokerage.get_wallets(account_ids)

    brokerage_get_wallets._ts_op_id = "C9"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C10 — GET /brokerage/stream/accounts/{accountIDs}/orders
# ---------------------------------------------------------------------------


def register_brokerage_stream_orders(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_stream_orders`` tool (C10)."""

    @mcp.tool(name="brokerage_stream_orders")
    async def brokerage_stream_orders(
        account_ids: list[str],
        max_events: int = 10,
    ) -> Any:
        """Stream live order events for one or more accounts (C10).

        Captures up to max_events order events and returns them as a list.

        Args:
            account_ids: List of account IDs.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.brokerage.stream_orders(account_ids), max_events=max_events
        )

    brokerage_stream_orders._ts_op_id = "C10"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C11 — GET /brokerage/stream/accounts/{accountIDs}/orders/{orderIDs}
# ---------------------------------------------------------------------------


def register_brokerage_stream_orders_by_id(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_stream_orders_by_id`` tool (C11)."""

    @mcp.tool(name="brokerage_stream_orders_by_id")
    async def brokerage_stream_orders_by_id(
        account_ids: list[str],
        order_ids: list[str],
        max_events: int = 10,
    ) -> Any:
        """Stream live events for specific orders (C11).

        Args:
            account_ids: List of account IDs.
            order_ids: List of order IDs.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.brokerage.stream_orders_by_id(account_ids, order_ids),
            max_events=max_events,
        )

    brokerage_stream_orders_by_id._ts_op_id = "C11"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C12 — GET /brokerage/stream/accounts/{accountIDs}/positions
# ---------------------------------------------------------------------------


def register_brokerage_stream_positions(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_stream_positions`` tool (C12)."""

    @mcp.tool(name="brokerage_stream_positions")
    async def brokerage_stream_positions(
        account_ids: list[str],
        max_events: int = 10,
    ) -> Any:
        """Stream live position updates for one or more accounts (C12).

        Args:
            account_ids: List of account IDs.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.brokerage.stream_positions(account_ids), max_events=max_events
        )

    brokerage_stream_positions._ts_op_id = "C12"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# C13 — GET /brokerage/stream/accounts/{accountIDs}/wallets
# ---------------------------------------------------------------------------


def register_brokerage_stream_wallets(mcp: FastMCP, client: Any) -> None:
    """Register the ``brokerage_stream_wallets`` tool (C13)."""

    @mcp.tool(name="brokerage_stream_wallets")
    async def brokerage_stream_wallets(
        account_ids: list[str],
        max_events: int = 10,
    ) -> Any:
        """Stream live wallet updates for one or more accounts (C13).

        Args:
            account_ids: List of account IDs.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.brokerage.stream_wallets(account_ids), max_events=max_events
        )

    brokerage_stream_wallets._ts_op_id = "C13"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Bulk registration
# ---------------------------------------------------------------------------

_REGISTRARS = [
    register_brokerage_list_accounts,
    register_brokerage_get_balances,
    register_brokerage_get_bod_balances,
    register_brokerage_get_positions,
    register_brokerage_get_orders,
    register_brokerage_get_orders_by_id,
    register_brokerage_get_historical_orders,
    register_brokerage_get_historical_orders_by_id,
    register_brokerage_get_wallets,
    register_brokerage_stream_orders,
    register_brokerage_stream_orders_by_id,
    register_brokerage_stream_positions,
    register_brokerage_stream_wallets,
]


def register_all(mcp: FastMCP, client: Any) -> None:
    """Register all C-series brokerage tools on *mcp*.

    Args:
        mcp: The FastMCP server instance.
        client: A ``TradeStationClient`` (or fake) providing ``.brokerage``.
    """
    for registrar in _REGISTRARS:
        registrar(mcp, client)
