"""Toolset allowlist groups for the MCP server.

See docs/06-mcp-server.md §"Toolset groups (allowlist)".

Toolsets:
    market    — all B-series tools (B1-B17)
    brokerage — all C-series tools (C1-C13)
    trading   — all D-series tools + auth_status
    auth      — auth_status only
    all       — all of the above (default)
"""

from __future__ import annotations

#: Canonical toolset names accepted by --toolsets.
VALID_TOOLSETS: frozenset[str] = frozenset({"market", "brokerage", "trading", "auth", "all"})

# ---------------------------------------------------------------------------
# Tool name sets per toolset group
# ---------------------------------------------------------------------------

#: Tools in the ``auth`` toolset.
AUTH_TOOLS: frozenset[str] = frozenset({"auth_status"})

#: Tools in the ``market`` toolset (B1-B17).
MARKET_TOOLS: frozenset[str] = frozenset(
    {
        # B-series REST (B1-B11)
        "market_data_get_bars",
        "market_data_get_quotes",
        "market_data_get_symbols",
        "market_data_list_symbol_lists",
        "market_data_get_symbol_list",
        "market_data_get_symbol_list_symbols",
        "market_data_list_crypto_pairs",
        "market_data_get_option_expirations",
        "market_data_get_option_strikes",
        "market_data_list_option_spread_types",
        "market_data_option_risk_reward",
        # B-series streaming (B12-B17)
        "market_data_stream_bars",
        "market_data_stream_quotes",
        "market_data_stream_depth_quotes",
        "market_data_stream_depth_aggregates",
        "market_data_stream_option_chain",
        "market_data_stream_option_quotes",
    }
)

#: Tools in the ``brokerage`` toolset (C1-C13).
BROKERAGE_TOOLS: frozenset[str] = frozenset(
    {
        # C-series REST (C1-C9)
        "brokerage_list_accounts",
        "brokerage_get_balances",
        "brokerage_get_bod_balances",
        "brokerage_get_positions",
        "brokerage_get_orders",
        "brokerage_get_orders_by_id",
        "brokerage_get_historical_orders",
        "brokerage_get_historical_orders_by_id",
        "brokerage_get_wallets",
        # C-series streaming (C10-C13)
        "brokerage_stream_orders",
        "brokerage_stream_orders_by_id",
        "brokerage_stream_positions",
        "brokerage_stream_wallets",
    }
)

#: Tools in the ``trading`` toolset (D1-D8).
TRADING_TOOLS: frozenset[str] = frozenset(
    {
        "order_confirm",
        "order_place",
        "order_replace",
        "order_cancel",
        "order_group_confirm",
        "order_group_place",
        "order_list_activation_triggers",
        "order_list_routes",
    }
)

#: All tools across every toolset.
ALL_TOOLS: frozenset[str] = AUTH_TOOLS | MARKET_TOOLS | BROKERAGE_TOOLS | TRADING_TOOLS

#: Destructive D-series tools that require the confirmation-token safety gate.
DESTRUCTIVE_TOOLS: frozenset[str] = frozenset(
    {
        "order_place",
        "order_replace",
        "order_cancel",
        "order_group_place",
    }
)


# ---------------------------------------------------------------------------
# Membership helpers
# ---------------------------------------------------------------------------


def resolve_toolsets(toolsets_csv: str) -> set[str]:
    """Parse the ``--toolsets`` CSV string into a canonical set of toolset names.

    ``"all"`` expands to ``{"market", "brokerage", "trading", "auth"}``.

    Args:
        toolsets_csv: Comma-separated toolset names (e.g. ``"market,brokerage"``).

    Returns:
        A set of resolved toolset name strings.

    Raises:
        ValueError: If an unrecognised toolset name is supplied.
    """
    parts = {s.strip().lower() for s in toolsets_csv.split(",") if s.strip()}
    unknown = parts - VALID_TOOLSETS
    if unknown:
        raise ValueError(
            f"Unknown toolset(s): {', '.join(sorted(unknown))}. "
            f"Valid options: {', '.join(sorted(VALID_TOOLSETS))}."
        )

    if "all" in parts:
        return {"market", "brokerage", "trading", "auth"}
    return parts


def active_tool_names(toolsets: set[str], *, read_only: bool = False) -> frozenset[str]:
    """Return the set of tool names that should be registered.

    Args:
        toolsets: Resolved toolset names (from :func:`resolve_toolsets`).
        read_only: If ``True``, D-series / trading tools are excluded entirely.

    Returns:
        Frozenset of MCP tool name strings to register.
    """
    names: set[str] = set()

    if "auth" in toolsets:
        names |= AUTH_TOOLS
    if "market" in toolsets:
        names |= MARKET_TOOLS
    if "brokerage" in toolsets:
        names |= BROKERAGE_TOOLS
    if "trading" in toolsets and not read_only:
        names |= TRADING_TOOLS

    return frozenset(names)


def enabled(name: str, toolsets: set[str], *, read_only: bool = False) -> bool:
    """Return whether tool *name* is active given *toolsets* and *read_only*.

    Args:
        name: MCP tool name to check.
        toolsets: Resolved toolset names.
        read_only: If ``True``, trading tools are blocked.

    Returns:
        ``True`` if the tool should be registered.
    """
    return name in active_tool_names(toolsets, read_only=read_only)
