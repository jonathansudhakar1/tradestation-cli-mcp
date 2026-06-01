"""Hand-crafted MCP tool ergonomic overrides.

See docs/06-mcp-server.md §"Hand-crafted overrides".

Overrides are needed for tools where auto-generated schemas are poor for LLMs:
    order_place          — flatten common shortcuts (--limit-price, etc.)
    option_risk_reward   — friendlier legs shape

At this phase, these are PLACEHOLDER overrides that return a structured
"not implemented at this phase" response.  Real bodies arrive when the
underlying service methods land in Phase 2.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

_NOT_IMPLEMENTED_MSG = (
    "This override is a placeholder for Phase 2. "
    "The real implementation will provide an improved UX once the underlying "
    "service methods are available."
)


def register_order_place_override(mcp: FastMCP, client: Any) -> None:
    """Register a hand-crafted ``order_place_override`` tool.

    This override flattens common order parameters (limit_price, stop_price)
    into top-level arguments for a friendlier LLM experience.

    At this phase it returns a placeholder response.

    Args:
        mcp: The FastMCP server instance.
        client: A ``TradeStationClient`` (or fake).
    """

    @mcp.tool(name="order_place_override")
    async def order_place_override(
        account_id: str,
        symbol: str,
        quantity: int,
        trade_action: str,
        order_type: str = "Market",
        limit_price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "DAY",
        route: str = "AUTO",
    ) -> dict[str, Any]:
        """Place a single order with a flattened, LLM-friendly parameter schema.

        This is a hand-crafted override for ``order_place`` (D2) that exposes
        common fields as top-level parameters rather than a nested request dict.

        Args:
            account_id: TradeStation account ID.
            symbol: Instrument symbol (e.g. AAPL, ES.M26, BTCUSD).
            quantity: Number of shares/contracts.
            trade_action: BUY, SELL, BUY_TO_OPEN, SELL_TO_CLOSE, etc.
            order_type: Market, Limit, StopMarket, StopLimit.
            limit_price: Limit price (required for Limit / StopLimit orders).
            stop_price: Stop price (required for StopMarket / StopLimit orders).
            time_in_force: DAY, GTC, GTD, IOC, FOK, OPG, CLO.
            route: Execution route (AUTO, ARCX, NSDQ, etc.).
        """
        return {
            "status": "not_implemented",
            "message": _NOT_IMPLEMENTED_MSG,
            "phase": "2c",
            "override": "order_place_override",
            "params": {
                "account_id": account_id,
                "symbol": symbol,
                "quantity": quantity,
                "trade_action": trade_action,
                "order_type": order_type,
                "limit_price": limit_price,
                "stop_price": stop_price,
                "time_in_force": time_in_force,
                "route": route,
            },
        }


def register_option_risk_reward_override(mcp: FastMCP, client: Any) -> None:
    """Register a hand-crafted ``option_risk_reward_override`` tool.

    This override accepts a friendlier ``legs: list[Leg]`` shape rather than
    the API's flat array format.

    At this phase it returns a placeholder response.

    Args:
        mcp: The FastMCP server instance.
        client: A ``TradeStationClient`` (or fake).
    """

    @mcp.tool(name="option_risk_reward_override")
    async def option_risk_reward_override(
        legs: list[dict[str, Any]],
        entry_price: float,
        underlying: str | None = None,
    ) -> dict[str, Any]:
        """Analyse risk/reward for a multi-leg option position (B11 override).

        Accepts a friendlier legs format where each leg is a dict with:
            symbol, expiry (YYYY-MM-DD), strike (float), option_type (C/P),
            quantity (int), open_price (float), action (BTO/STO/BTC/STC).

        Args:
            legs: List of option leg dicts.
            entry_price: Net entry price for the spread.
            underlying: Underlying symbol hint (e.g. AAPL).
        """
        return {
            "status": "not_implemented",
            "message": _NOT_IMPLEMENTED_MSG,
            "phase": "2c",
            "override": "option_risk_reward_override",
            "params": {
                "legs": legs,
                "entry_price": entry_price,
                "underlying": underlying,
            },
        }


def register_all_overrides(mcp: FastMCP, client: Any) -> None:
    """Register all hand-crafted override tools on *mcp*.

    Args:
        mcp: The FastMCP server instance.
        client: A ``TradeStationClient`` (or fake).
    """
    register_order_place_override(mcp, client)
    register_option_risk_reward_override(mcp, client)
