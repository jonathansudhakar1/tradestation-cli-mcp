"""Market data MCP tools (B-series).

Each ``register_*`` function registers one MCP tool on the given FastMCP
server.  Handlers delegate to ``client.market_data.<method>`` and return the
result.  The underlying service methods may raise ``NotImplementedError`` at
this phase — the MCP layer just routes.

Inventory coverage: B1-B17 (17 tools).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from tradestation.mcp._collect import collect_stream

# ---------------------------------------------------------------------------
# B1 — GET /marketdata/barcharts/{symbol}
# ---------------------------------------------------------------------------


def register_market_data_get_bars(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_bars`` tool (B1)."""

    @mcp.tool(name="market_data_get_bars")
    async def market_data_get_bars(
        symbol: str,
        interval: int = 1,
        unit: str = "Minute",
        barsback: int | None = None,
        firstdate: str | None = None,
        lastdate: str | None = None,
        session_template: str = "Default",
    ) -> Any:
        """Fetch historical bar chart data (B1).

        Args:
            symbol: Instrument symbol (e.g. AAPL, ES.M26).
            interval: Bar size; meaning depends on unit.
            unit: Bar unit: Minute, Daily, Weekly, Monthly, Tick, Volume.
            barsback: Number of bars to return counting back from lastdate.
            firstdate: ISO-8601 start date/datetime (inclusive).
            lastdate: ISO-8601 end date/datetime (inclusive).
            session_template: Session template: Default, USEQPreAndPost, etc.
        """
        return await client.market_data.get_bars(
            symbol,
            interval=interval,
            unit=unit,
            barsback=barsback,
            firstdate=firstdate,
            lastdate=lastdate,
            session_template=session_template,
        )

    market_data_get_bars._ts_op_id = "B1"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B2 — GET /marketdata/quotes/{symbols}
# ---------------------------------------------------------------------------


def register_market_data_get_quotes(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_quotes`` tool (B2)."""

    @mcp.tool(name="market_data_get_quotes")
    async def market_data_get_quotes(
        symbols: list[str],
    ) -> Any:
        """Fetch quote snapshots for one or more symbols (B2).

        Args:
            symbols: List of instrument symbols (e.g. ["AAPL", "MSFT", "BTCUSD"]).
        """
        return await client.market_data.get_quotes(symbols)

    market_data_get_quotes._ts_op_id = "B2"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B3 — GET /marketdata/symbols/{symbols}
# ---------------------------------------------------------------------------


def register_market_data_get_symbols(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_symbols`` tool (B3)."""

    @mcp.tool(name="market_data_get_symbols")
    async def market_data_get_symbols(
        symbols: list[str],
    ) -> Any:
        """Fetch symbol metadata for one or more symbols (B3).

        Args:
            symbols: List of instrument symbols.
        """
        return await client.market_data.get_symbols(symbols)

    market_data_get_symbols._ts_op_id = "B3"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B4 — GET /marketdata/symbollists
# ---------------------------------------------------------------------------


def register_market_data_list_symbol_lists(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_list_symbol_lists`` tool (B4)."""

    @mcp.tool(name="market_data_list_symbol_lists")
    async def market_data_list_symbol_lists() -> Any:
        """List the authenticated user's symbol lists (B4)."""
        return await client.market_data.list_symbol_lists()

    market_data_list_symbol_lists._ts_op_id = "B4"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B5 — GET /marketdata/symbollists/{symbolListID}
# ---------------------------------------------------------------------------


def register_market_data_get_symbol_list(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_symbol_list`` tool (B5)."""

    @mcp.tool(name="market_data_get_symbol_list")
    async def market_data_get_symbol_list(
        list_id: str,
    ) -> Any:
        """Fetch a single symbol list by ID (B5).

        Args:
            list_id: Symbol list identifier.
        """
        return await client.market_data.get_symbol_list(list_id)

    market_data_get_symbol_list._ts_op_id = "B5"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B6 — GET /marketdata/symbollists/{symbolListID}/symbols
# ---------------------------------------------------------------------------


def register_market_data_get_symbol_list_symbols(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_symbol_list_symbols`` tool (B6)."""

    @mcp.tool(name="market_data_get_symbol_list_symbols")
    async def market_data_get_symbol_list_symbols(
        list_id: str,
    ) -> Any:
        """Fetch the symbols inside a symbol list (B6).

        Args:
            list_id: Symbol list identifier.
        """
        return await client.market_data.get_symbol_list_symbols(list_id)

    market_data_get_symbol_list_symbols._ts_op_id = "B6"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B7 — GET /marketdata/crypto/symbolnames
# ---------------------------------------------------------------------------


def register_market_data_list_crypto_pairs(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_list_crypto_pairs`` tool (B7)."""

    @mcp.tool(name="market_data_list_crypto_pairs")
    async def market_data_list_crypto_pairs() -> Any:
        """List all supported cryptocurrency trading pairs (B7)."""
        return await client.market_data.list_crypto_pairs()

    market_data_list_crypto_pairs._ts_op_id = "B7"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B8 — GET /marketdata/options/expirations/{underlying}
# ---------------------------------------------------------------------------


def register_market_data_get_option_expirations(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_option_expirations`` tool (B8)."""

    @mcp.tool(name="market_data_get_option_expirations")
    async def market_data_get_option_expirations(
        underlying: str,
        strike: float | None = None,
    ) -> Any:
        """Fetch available option expiration dates for an underlying (B8).

        Args:
            underlying: Underlying symbol (e.g. AAPL).
            strike: Optional strike price filter.
        """
        return await client.market_data.get_option_expirations(underlying, strike=strike)

    market_data_get_option_expirations._ts_op_id = "B8"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B9 — GET /marketdata/options/strikes/{underlying}
# ---------------------------------------------------------------------------


def register_market_data_get_option_strikes(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_get_option_strikes`` tool (B9)."""

    @mcp.tool(name="market_data_get_option_strikes")
    async def market_data_get_option_strikes(
        underlying: str,
        expiration: str | None = None,
        spread_type: str | None = None,
    ) -> Any:
        """Fetch available option strike prices for an underlying (B9).

        Args:
            underlying: Underlying symbol.
            expiration: Expiration date filter (ISO-8601 date string).
            spread_type: Spread type filter.
        """
        return await client.market_data.get_option_strikes(
            underlying,
            expiration=expiration,
            spread_type=spread_type,
        )

    market_data_get_option_strikes._ts_op_id = "B9"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B10 — GET /marketdata/options/spreadtypes
# ---------------------------------------------------------------------------


def register_market_data_list_option_spread_types(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_list_option_spread_types`` tool (B10)."""

    @mcp.tool(name="market_data_list_option_spread_types")
    async def market_data_list_option_spread_types() -> Any:
        """List all supported option spread types (B10)."""
        return await client.market_data.list_option_spread_types()

    market_data_list_option_spread_types._ts_op_id = "B10"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B11 — POST /marketdata/options/riskreward
# ---------------------------------------------------------------------------


def register_market_data_option_risk_reward(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_option_risk_reward`` tool (B11)."""

    @mcp.tool(name="market_data_option_risk_reward")
    async def market_data_option_risk_reward(
        legs: list[dict[str, Any]],
        entry: float,
    ) -> Any:
        """Compute risk/reward analysis for a multi-leg option position (B11).

        Args:
            legs: List of option legs (each a dict with symbol, expiry, strike,
                option_type, quantity, open_price fields).
            entry: Net entry price for the spread.
        """
        return await client.market_data.option_risk_reward(legs, entry=entry)

    market_data_option_risk_reward._ts_op_id = "B11"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B12 — GET /marketdata/stream/barcharts/{symbol}
# ---------------------------------------------------------------------------


def register_market_data_stream_bars(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_stream_bars`` tool (B12)."""

    @mcp.tool(name="market_data_stream_bars")
    async def market_data_stream_bars(
        symbol: str,
        interval: int = 1,
        unit: str = "Minute",
        session_template: str = "Default",
        max_events: int = 10,
    ) -> Any:
        """Stream live bar updates for a symbol (B12).

        Captures up to max_events bar events and returns them as a list.

        Args:
            symbol: Instrument symbol (e.g. AAPL, ES.M26).
            interval: Bar size.
            unit: Bar unit: Minute, Daily, Weekly, Monthly, Tick, Volume.
            session_template: Session template.
            max_events: Maximum number of events to collect before returning.
        """
        from tradestation.enums import BarUnit, MarketSession

        return await collect_stream(
            client.market_data.stream_bars(
                symbol,
                interval=interval,
                unit=BarUnit(unit),
                session_template=MarketSession(session_template),
            ),
            max_events=max_events,
        )

    market_data_stream_bars._ts_op_id = "B12"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B13 — GET /marketdata/stream/quotes/{symbols}
# ---------------------------------------------------------------------------


def register_market_data_stream_quotes(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_stream_quotes`` tool (B13)."""

    @mcp.tool(name="market_data_stream_quotes")
    async def market_data_stream_quotes(
        symbols: list[str],
        max_events: int = 10,
    ) -> Any:
        """Stream live quote updates for one or more symbols (B13).

        Captures up to max_events quote events and returns them as a list.

        Args:
            symbols: List of instrument symbols.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.market_data.stream_quotes(symbols), max_events=max_events
        )

    market_data_stream_quotes._ts_op_id = "B13"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B14 — GET /marketdata/stream/marketdepth/quotes/{symbol}
# ---------------------------------------------------------------------------


def register_market_data_stream_depth_quotes(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_stream_depth_quotes`` tool (B14)."""

    @mcp.tool(name="market_data_stream_depth_quotes")
    async def market_data_stream_depth_quotes(
        symbol: str,
        max_events: int = 10,
    ) -> Any:
        """Stream Level-2 individual market-depth quotes (B14).

        Args:
            symbol: Instrument symbol.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.market_data.stream_depth_quotes(symbol), max_events=max_events
        )

    market_data_stream_depth_quotes._ts_op_id = "B14"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B15 — GET /marketdata/stream/marketdepth/aggregates/{symbol}
# ---------------------------------------------------------------------------


def register_market_data_stream_depth_aggregates(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_stream_depth_aggregates`` tool (B15)."""

    @mcp.tool(name="market_data_stream_depth_aggregates")
    async def market_data_stream_depth_aggregates(
        symbol: str,
        max_events: int = 10,
    ) -> Any:
        """Stream Level-2 aggregate market-depth data (B15).

        Args:
            symbol: Instrument symbol.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.market_data.stream_depth_aggregates(symbol), max_events=max_events
        )

    market_data_stream_depth_aggregates._ts_op_id = "B15"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B16 — GET /marketdata/stream/options/chains/{underlying}
# ---------------------------------------------------------------------------


def register_market_data_stream_option_chain(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_stream_option_chain`` tool (B16)."""

    @mcp.tool(name="market_data_stream_option_chain")
    async def market_data_stream_option_chain(
        underlying: str,
        expiration: str,
        max_events: int = 10,
    ) -> Any:
        """Stream live option chain data for an underlying (B16).

        Args:
            underlying: Underlying symbol.
            expiration: Expiration date (ISO-8601).
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.market_data.stream_option_chain(underlying, expiration),
            max_events=max_events,
        )

    market_data_stream_option_chain._ts_op_id = "B16"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B17 — GET /marketdata/stream/options/quotes
# ---------------------------------------------------------------------------


def register_market_data_stream_option_quotes(mcp: FastMCP, client: Any) -> None:
    """Register the ``market_data_stream_option_quotes`` tool (B17)."""

    @mcp.tool(name="market_data_stream_option_quotes")
    async def market_data_stream_option_quotes(
        legs: list[dict[str, Any]],
        max_events: int = 10,
    ) -> Any:
        """Stream live option quote data for specified legs (B17).

        Args:
            legs: List of option legs identifying strikes/expirations.
            max_events: Maximum number of events to collect before returning.
        """
        return await collect_stream(
            client.market_data.stream_option_quotes(legs), max_events=max_events
        )

    market_data_stream_option_quotes._ts_op_id = "B17"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Bulk registration
# ---------------------------------------------------------------------------

_REGISTRARS = [
    register_market_data_get_bars,
    register_market_data_get_quotes,
    register_market_data_get_symbols,
    register_market_data_list_symbol_lists,
    register_market_data_get_symbol_list,
    register_market_data_get_symbol_list_symbols,
    register_market_data_list_crypto_pairs,
    register_market_data_get_option_expirations,
    register_market_data_get_option_strikes,
    register_market_data_list_option_spread_types,
    register_market_data_option_risk_reward,
    register_market_data_stream_bars,
    register_market_data_stream_quotes,
    register_market_data_stream_depth_quotes,
    register_market_data_stream_depth_aggregates,
    register_market_data_stream_option_chain,
    register_market_data_stream_option_quotes,
]


def register_all(mcp: FastMCP, client: Any) -> None:
    """Register all B-series market data tools on *mcp*.

    Args:
        mcp: The FastMCP server instance.
        client: A ``TradeStationClient`` (or fake) providing ``.market_data``.
    """
    for registrar in _REGISTRARS:
        registrar(mcp, client)
