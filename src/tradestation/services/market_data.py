"""MarketDataService — all B-series endpoint methods.

See docs/03-endpoint-inventory.md §"B. MarketData" for the full inventory.
See docs/05-python-library.md §"Service surface" for method signatures.

All methods raise ``NotImplementedError`` in Phase 0 (scaffolding only).
Implementation tracked in Phase 2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from tradestation.enums import BarUnit, MarketSession
from tradestation.models.market_data import (
    Bar,
    Quote,
    parse_bars_response,
    parse_quotes_response,
)
from tradestation.services.base import BaseService
from tradestation.streaming import StreamEvent


class MarketDataService(BaseService):
    """Service wrapping all TradeStation MarketData v3 endpoints (B1-B17).

    Obtain via ``client.market_data`` — do not construct directly.
    """

    # ------------------------------------------------------------------
    # B.1 — REST endpoints
    # ------------------------------------------------------------------

    async def get_bars(
        self,
        symbol: str,
        *,
        interval: int = 1,
        unit: BarUnit = BarUnit.MINUTE,
        barsback: int | None = None,
        firstdate: str | None = None,
        lastdate: str | None = None,
        session_template: MarketSession = MarketSession.DEFAULT,
    ) -> list[Bar]:
        """Fetch historical bar chart data.

        Maps to: B1 GET /v3/marketdata/barcharts/{symbol}

        Args:
            symbol: Instrument symbol (e.g. ``"AAPL"``, ``"ESM26"``, ``"BTCUSD"``).
            interval: Bar size; meaning depends on *unit*.
            unit: Bar unit (Minute, Daily, Weekly, Monthly, Tick, Volume).
            barsback: Number of bars to return counting back from *lastdate*.
            firstdate: ISO-8601 start date/datetime (inclusive).
            lastdate: ISO-8601 end date/datetime (inclusive).
            session_template: Which session(s) to include.

        Returns:
            A list of :class:`~tradestation.models.market_data.Bar` models in
            chronological order.

        Raises:
            tradestation.errors.ApiError: On 4xx / 5xx from the API.
            tradestation.errors.NetworkError: On transport failure.
        """
        params: dict[str, Any] = {
            "interval": interval,
            "unit": unit.value,
            "sessiontemplate": session_template.value,
        }
        if barsback is not None:
            params["barsback"] = barsback
        if firstdate is not None:
            params["firstdate"] = firstdate
        if lastdate is not None:
            params["lastdate"] = lastdate
        raw = await self._transport.request(
            "GET", f"/marketdata/barcharts/{symbol}", params=params
        )
        return parse_bars_response(raw)

    async def get_quotes(self, symbols: list[str] | str) -> list[Quote]:
        """Fetch quote snapshots for one or more symbols.

        Maps to: B2 GET /v3/marketdata/quotes/{symbols}

        Args:
            symbols: List of instrument symbols (or a single comma-separated
                string).  Joined as a comma-separated path segment.

        Returns:
            A list of :class:`~tradestation.models.market_data.Quote` models,
            one per valid symbol.  Symbols with errors are omitted.

        Raises:
            tradestation.errors.ApiError: On 4xx / 5xx from the API.
            tradestation.errors.NetworkError: On transport failure.
        """
        if isinstance(symbols, str):
            # Accept "AAPL,MSFT" as well as ["AAPL", "MSFT"]
            syms = [s.strip() for s in symbols.split(",") if s.strip()]
        else:
            syms = list(symbols)

        path = "/marketdata/quotes/" + ",".join(syms)
        raw = await self._transport.request("GET", path)
        return parse_quotes_response(raw)

    async def get_symbols(self, symbols: list[str]) -> Any:
        """Fetch symbol metadata for one or more symbols.

        Maps to: B3 GET /marketdata/symbols/{symbols}

        Args:
            symbols: List of instrument symbols.

        Returns:
            Parsed symbol-detail response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B3")

    async def list_symbol_lists(self) -> Any:
        """List the authenticated user's symbol lists.

        Maps to: B4 GET /marketdata/symbollists

        Returns:
            Parsed symbol-list collection (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B4")

    async def get_symbol_list(self, list_id: str) -> Any:
        """Fetch a single symbol list by ID.

        Maps to: B5 GET /marketdata/symbollists/{symbolListID}

        Args:
            list_id: Symbol list identifier.

        Returns:
            Parsed symbol-list detail (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B5")

    async def get_symbol_list_symbols(self, list_id: str) -> Any:
        """Fetch the symbols inside a symbol list.

        Maps to: B6 GET /marketdata/symbollists/{symbolListID}/symbols

        Args:
            list_id: Symbol list identifier.

        Returns:
            Parsed symbol collection (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B6")

    async def list_crypto_pairs(self) -> Any:
        """List all supported cryptocurrency trading pairs.

        Maps to: B7 GET /marketdata/crypto/symbolnames

        Returns:
            Parsed crypto-pair list (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B7")

    async def get_option_expirations(
        self,
        underlying: str,
        *,
        strike: float | None = None,
    ) -> Any:
        """Fetch available option expiration dates for an underlying.

        Maps to: B8 GET /marketdata/options/expirations/{underlying}

        Args:
            underlying: Underlying symbol (e.g. ``"AAPL"``).
            strike: Optional strike price filter.

        Returns:
            Parsed expirations response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B8")

    async def get_option_strikes(
        self,
        underlying: str,
        *,
        expiration: str | None = None,
        spread_type: str | None = None,
    ) -> Any:
        """Fetch available option strike prices for an underlying.

        Maps to: B9 GET /marketdata/options/strikes/{underlying}

        Args:
            underlying: Underlying symbol.
            expiration: Expiration date filter (ISO-8601 date string).
            spread_type: Spread type filter.

        Returns:
            Parsed strikes response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B9")

    async def list_option_spread_types(self) -> Any:
        """List all supported option spread types.

        Maps to: B10 GET /marketdata/options/spreadtypes

        Returns:
            Parsed spread-types list (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B10")

    async def option_risk_reward(
        self,
        legs: list[dict[str, Any]],
        *,
        entry: float,
    ) -> Any:
        """Compute risk/reward analysis for a multi-leg option position.

        Maps to: B11 POST /marketdata/options/riskreward

        Args:
            legs: List of option legs (structure TBD — Phase 2).
            entry: Net entry price for the spread.

        Returns:
            Parsed risk/reward response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' B11")

    # ------------------------------------------------------------------
    # B.2 — Streaming endpoints
    # ------------------------------------------------------------------

    async def stream_bars(
        self,
        symbol: str,
        *,
        interval: int = 1,
        unit: BarUnit = BarUnit.MINUTE,
        session_template: MarketSession = MarketSession.DEFAULT,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live bar updates for a symbol.

        Maps to: B12 GET /marketdata/stream/barcharts/{symbol}

        Args:
            symbol: Instrument symbol.
            interval: Bar size.
            unit: Bar unit.
            session_template: Session filter.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' B12")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

    async def stream_quotes(
        self,
        symbols: list[str],
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live quote updates for one or more symbols.

        Maps to: B13 GET /marketdata/stream/quotes/{symbols}

        Args:
            symbols: List of instrument symbols.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' B13")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

    async def stream_depth_quotes(
        self,
        symbol: str,
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream Level-2 individual market-depth quotes.

        Maps to: B14 GET /marketdata/stream/marketdepth/quotes/{symbol}

        Args:
            symbol: Instrument symbol.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' B14")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

    async def stream_depth_aggregates(
        self,
        symbol: str,
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream Level-2 aggregate market-depth data.

        Maps to: B15 GET /marketdata/stream/marketdepth/aggregates/{symbol}

        Args:
            symbol: Instrument symbol.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' B15")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

    async def stream_option_chain(
        self,
        underlying: str,
        expiration: str,
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live option chain data for an underlying.

        Maps to: B16 GET /marketdata/stream/options/chains/{underlying}

        Args:
            underlying: Underlying symbol.
            expiration: Expiration date (ISO-8601).
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' B16")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

    async def stream_option_quotes(
        self,
        legs: list[dict[str, Any]],
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live option quote data for specified legs.

        Maps to: B17 GET /marketdata/stream/options/quotes

        Args:
            legs: List of option legs identifying strikes/expirations.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' B17")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover
