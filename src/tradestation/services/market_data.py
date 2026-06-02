"""MarketDataService — all B-series endpoint methods.

See docs/03-endpoint-inventory.md §"B. MarketData" for the full inventory.
See docs/05-python-library.md §"Service surface" for method signatures.

Covers the REST endpoints (B1-B11) and streaming endpoints (B12-B17).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from tradestation.enums import BarUnit, MarketSession
from tradestation.models.market_data import (
    Bar,
    OptionExpiration,
    OptionSpreadType,
    Quote,
    Symbol,
    SymbolList,
    parse_bars_response,
    parse_option_expirations_response,
    parse_option_spread_types_response,
    parse_quotes_response,
    parse_symbol_lists_response,
    parse_symbols_response,
)
from tradestation.services.base import BaseService
from tradestation.streaming import StreamEvent, stream_events


def _split_symbols(symbols: list[str] | str) -> list[str]:
    """Normalise a symbol argument (list or CSV string) to a list."""
    if isinstance(symbols, str):
        return [s.strip() for s in symbols.split(",") if s.strip()]
    return list(symbols)


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
        raw = await self._transport.request("GET", f"/marketdata/barcharts/{symbol}", params=params)
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

    async def get_symbols(self, symbols: list[str] | str) -> list[Symbol]:
        """Fetch symbol metadata for one or more symbols.

        Maps to: B3 GET /v3/marketdata/symbols/{symbols}

        Args:
            symbols: Instrument symbols (list or comma-separated string).

        Returns:
            A list of :class:`~tradestation.models.market_data.Symbol` models.
        """
        syms = _split_symbols(symbols)
        raw = await self._transport.request("GET", "/marketdata/symbols/" + ",".join(syms))
        return parse_symbols_response(raw)

    async def list_symbol_lists(self) -> list[SymbolList]:
        """List the authenticated user's symbol lists.

        Maps to: B4 GET /v3/marketdata/symbollists

        Returns:
            A list of :class:`~tradestation.models.market_data.SymbolList` models.
        """
        raw = await self._transport.request("GET", "/marketdata/symbollists")
        return parse_symbol_lists_response(raw)

    async def get_symbol_list(self, list_id: str) -> SymbolList:
        """Fetch a single symbol list by ID.

        Maps to: B5 GET /v3/marketdata/symbollists/{symbolListID}

        Args:
            list_id: Symbol list identifier.

        Returns:
            The :class:`~tradestation.models.market_data.SymbolList`.
        """
        raw = await self._transport.request("GET", f"/marketdata/symbollists/{list_id}")
        return SymbolList.model_validate(raw)

    async def get_symbol_list_symbols(self, list_id: str) -> list[Symbol]:
        """Fetch the symbols inside a symbol list.

        Maps to: B6 GET /v3/marketdata/symbollists/{symbolListID}/symbols

        Args:
            list_id: Symbol list identifier.

        Returns:
            A list of :class:`~tradestation.models.market_data.Symbol` models.
        """
        raw = await self._transport.request("GET", f"/marketdata/symbollists/{list_id}/symbols")
        return parse_symbols_response(raw)

    async def list_crypto_pairs(self) -> list[str]:
        """List all supported cryptocurrency trading pairs.

        Maps to: B7 GET /v3/marketdata/crypto/symbolnames

        Returns:
            A list of crypto symbol-name strings (e.g. ``["BTCUSD", "ETHUSD"]``).
        """
        raw = await self._transport.request(
            "GET", "/marketdata/symbollists/cryptopairs/symbolnames"
        )
        names = raw.get("SymbolNames") or raw.get("Cryptocurrencies") or []
        return [str(n) for n in names] if isinstance(names, list) else []

    async def get_option_expirations(
        self,
        underlying: str,
        *,
        strike: float | None = None,
    ) -> list[OptionExpiration]:
        """Fetch available option expiration dates for an underlying.

        Maps to: B8 GET /v3/marketdata/options/expirations/{underlying}

        Args:
            underlying: Underlying symbol (e.g. ``"AAPL"``).
            strike: Optional strike price filter.

        Returns:
            A list of :class:`~tradestation.models.market_data.OptionExpiration`.
        """
        params = {"strikePrice": strike} if strike is not None else None
        raw = await self._transport.request(
            "GET", f"/marketdata/options/expirations/{underlying}", params=params
        )
        return parse_option_expirations_response(raw)

    async def get_option_strikes(
        self,
        underlying: str,
        *,
        expiration: str | None = None,
        spread_type: str | None = None,
    ) -> dict[str, Any]:
        """Fetch available option strike prices for an underlying.

        Maps to: B9 GET /v3/marketdata/options/strikes/{underlying}

        The response is ``{"SpreadType": "...", "Strikes": [[...], ...]}`` —
        each inner list is a strike grouping. Returned as a raw dict so callers
        can interpret the nested structure directly.

        Args:
            underlying: Underlying symbol.
            expiration: Expiration date filter (ISO-8601 date string).
            spread_type: Spread type filter.

        Returns:
            The raw strikes response dict.
        """
        params: dict[str, Any] = {}
        if expiration is not None:
            params["expiration"] = expiration
        if spread_type is not None:
            params["spreadType"] = spread_type
        return await self._transport.request(
            "GET",
            f"/marketdata/options/strikes/{underlying}",
            params=params or None,
        )

    async def list_option_spread_types(self) -> list[OptionSpreadType]:
        """List all supported option spread types.

        Maps to: B10 GET /v3/marketdata/options/spreadtypes

        Returns:
            A list of :class:`~tradestation.models.market_data.OptionSpreadType`.
        """
        raw = await self._transport.request("GET", "/marketdata/options/spreadtypes")
        return parse_option_spread_types_response(raw)

    async def option_risk_reward(
        self,
        legs: list[dict[str, Any]],
        *,
        entry: float,
    ) -> dict[str, Any]:
        """Compute risk/reward analysis for a multi-leg option position.

        Maps to: B11 POST /v3/marketdata/options/riskreward

        Args:
            legs: Option legs, each like
                ``{"Symbol": "AAPL 260620C200", "Ratio": 1, "OpenPrice": "5.40"}``.
            entry: Net entry price (``SpreadPrice``) for the spread.

        Returns:
            The raw risk/reward response dict (MaxGain, MaxLoss, RiskRewardRatio…).
        """
        body = {"SpreadPrice": str(entry), "Legs": legs}
        return await self._transport.request("POST", "/marketdata/options/riskreward", json=body)

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
        """
        params = {
            "interval": interval,
            "unit": unit.value,
            "sessiontemplate": session_template.value,
        }
        async for event in stream_events(
            self._transport,
            f"/marketdata/stream/barcharts/{symbol}",
            params=params,
            include_heartbeats=include_heartbeats,
        ):
            yield event

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
        """
        async for event in stream_events(
            self._transport,
            "/marketdata/stream/quotes/" + ",".join(_split_symbols(symbols)),
            include_heartbeats=include_heartbeats,
        ):
            yield event

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
        """
        async for event in stream_events(
            self._transport,
            f"/marketdata/stream/marketdepth/quotes/{symbol}",
            include_heartbeats=include_heartbeats,
        ):
            yield event

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
        """
        async for event in stream_events(
            self._transport,
            f"/marketdata/stream/marketdepth/aggregates/{symbol}",
            include_heartbeats=include_heartbeats,
        ):
            yield event

    async def stream_option_chain(
        self,
        underlying: str,
        expiration: str,
        *,
        strike_proximity: int | None = None,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live option chain data for an underlying.

        Maps to: B16 GET /marketdata/stream/options/chains/{underlying}

        Args:
            underlying: Underlying symbol.
            expiration: Expiration date (ISO-8601).
            strike_proximity: Number of strikes to return *above and below* the
                at-the-money strike. The server defaults to a small window
                (~5 each side), so pass this to widen the chain. ``None`` uses
                the server default.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.
        """
        params: dict[str, Any] = {}
        if expiration:
            params["expiration"] = expiration
        if strike_proximity is not None:
            params["strikeProximity"] = strike_proximity
        async for event in stream_events(
            self._transport,
            f"/marketdata/stream/options/chains/{underlying}",
            params=params or None,
            include_heartbeats=include_heartbeats,
        ):
            yield event

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
        """
        params: dict[str, Any] = {}
        for i, leg in enumerate(legs):
            sym = leg.get("Symbol") or leg.get("symbol")
            if sym:
                params[f"legs[{i}].Symbol"] = sym
        async for event in stream_events(
            self._transport,
            "/marketdata/stream/options/quotes",
            params=params or None,
            include_heartbeats=include_heartbeats,
        ):
            yield event
