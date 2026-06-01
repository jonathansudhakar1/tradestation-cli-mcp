"""Unit tests for MarketDataService.get_quotes (B2).

Uses respx to mock HTTP; no real network calls.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from tradestation.credentials import Credentials
from tradestation.enums import Environment
from tradestation.errors import ApiError, NetworkError, NotFoundError
from tradestation.models.market_data import Quote
from tradestation.services.market_data import MarketDataService
from tradestation.transport import Transport

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

_BASE = "https://sim-api.tradestation.com/v3"

_CANNED_AAPL = {
    "Symbol": "AAPL",
    "Last": "178.45",
    "Bid": "178.44",
    "BidSize": "400",
    "Ask": "178.46",
    "AskSize": "300",
    "Open": "177.10",
    "High": "179.02",
    "Low": "176.81",
    "Close": "178.45",
    "PreviousClose": "177.18",
    "NetChange": "1.27",
    "NetChangePct": "0.72",
    "Volume": "42113800",
    "TradeTime": "2026-06-01T16:30:00Z",
    "MarketFlags": {
        "IsHalted": False,
        "IsDelayed": False,
        "IsHardToBorrow": False,
        "IsBats": False,
    },
    "VWAP": "178.12",
    "LastSize": "100",
    "LastVenue": "TRF",
}

_CANNED_MSFT = {
    "Symbol": "MSFT",
    "Last": "431.10",
    "Bid": "431.09",
    "Ask": "431.12",
    "NetChange": "-0.85",
    "NetChangePct": "-0.20",
    "Volume": "18402140",
    "Open": "432.00",
    "High": "432.90",
    "Low": "430.55",
    "TradeTime": "2026-06-01T16:30:00Z",
    "MarketFlags": {"IsHalted": False, "IsDelayed": False},
}

_CANNED_BTCUSD = {
    "Symbol": "BTCUSD",
    "Last": "71235.78",
    "Bid": "0",
    "Ask": "0",
    "NetChange": "-2340.728",
    "NetChangePct": "-3.18",
    "Volume": "691",
    "Open": "73632.023",
    "High": "74092.078",
    "Low": "70555",
    "TradeTime": "2026-06-01T16:30:00Z",
    "MarketFlags": {"IsHalted": False, "IsDelayed": False},
}


def _make_transport(http_client: httpx.AsyncClient) -> Transport:
    """Create a Transport with a fake auth manager (no real token exchange)."""
    creds = Credentials(
        client_id="FAKE",
        client_secret="FAKE",
        refresh_token="FAKE",
        environment=Environment.SIM,
        access_token="FAKE_TOKEN",
        access_token_expires_at="2099-01-01T00:00:00Z",
    )
    return Transport(creds, http_client=http_client)


def _quotes_response(*quote_dicts: dict) -> dict:
    return {"Quotes": list(quote_dicts)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetQuotesSingleSymbol:
    @pytest.mark.asyncio
    @respx.mock
    async def test_single_symbol_aapl(self) -> None:
        """get_quotes(['AAPL']) calls the correct URL and parses the response."""
        respx.get(f"{_BASE}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(
                200,
                json=_quotes_response(_CANNED_AAPL),
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            quotes = await svc.get_quotes(["AAPL"])

        assert len(quotes) == 1
        q = quotes[0]
        assert isinstance(q, Quote)
        assert q.symbol == "AAPL"
        assert q.last == pytest.approx(178.45)
        assert q.bid == pytest.approx(178.44)
        assert q.ask == pytest.approx(178.46)
        assert q.net_change == pytest.approx(1.27)
        assert q.volume == 42113800
        assert q.market_flags is not None
        assert q.market_flags.is_halted is False
        # Extra fields stored in __pydantic_extra__
        assert q.last_utc is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_string_form_accepted(self) -> None:
        """get_quotes('AAPL,MSFT') accepts a CSV string."""
        respx.get(f"{_BASE}/marketdata/quotes/AAPL,MSFT").mock(
            return_value=httpx.Response(
                200,
                json=_quotes_response(_CANNED_AAPL, _CANNED_MSFT),
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            quotes = await svc.get_quotes("AAPL,MSFT")

        assert len(quotes) == 2
        assert quotes[0].symbol == "AAPL"
        assert quotes[1].symbol == "MSFT"


class TestGetQuotesMultiSymbol:
    @pytest.mark.asyncio
    @respx.mock
    async def test_multi_symbol_list(self) -> None:
        """get_quotes(['AAPL','MSFT','BTCUSD']) joins symbols and parses all."""
        respx.get(f"{_BASE}/marketdata/quotes/AAPL,MSFT,BTCUSD").mock(
            return_value=httpx.Response(
                200,
                json=_quotes_response(_CANNED_AAPL, _CANNED_MSFT, _CANNED_BTCUSD),
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            quotes = await svc.get_quotes(["AAPL", "MSFT", "BTCUSD"])

        assert len(quotes) == 3
        syms = [q.symbol for q in quotes]
        assert "AAPL" in syms
        assert "MSFT" in syms
        assert "BTCUSD" in syms

    @pytest.mark.asyncio
    @respx.mock
    async def test_crypto_large_price(self) -> None:
        """BTCUSD at ~71k parses correctly (no overflow / rounding issues)."""
        respx.get(f"{_BASE}/marketdata/quotes/BTCUSD").mock(
            return_value=httpx.Response(
                200,
                json=_quotes_response(_CANNED_BTCUSD),
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            quotes = await svc.get_quotes(["BTCUSD"])

        q = quotes[0]
        assert q.last == pytest.approx(71235.78)
        assert q.last_utc is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_futures_symbol(self) -> None:
        """@ES symbol with large price parses correctly."""
        es_quote = {
            "Symbol": "@ES",
            "Last": "5318.50",
            "Bid": "5318.25",
            "Ask": "5318.75",
            "NetChange": "18.50",
            "NetChangePct": "0.35",
            "Volume": "125000",
            "Open": "5300.00",
            "High": "5325.00",
            "Low": "5295.00",
            "TradeTime": "2026-06-01T16:30:00Z",
            "MarketFlags": {"IsHalted": False},
        }
        respx.get(f"{_BASE}/marketdata/quotes/@ES").mock(
            return_value=httpx.Response(
                200,
                json=_quotes_response(es_quote),
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            quotes = await svc.get_quotes(["@ES"])

        q = quotes[0]
        assert q.symbol == "@ES"
        assert q.last == pytest.approx(5318.50)


class TestGetQuotesErrors:
    @pytest.mark.asyncio
    @respx.mock
    async def test_404_bad_symbol_raises_api_error(self) -> None:
        """404 on a bad symbol raises ApiError / NotFoundError."""
        respx.get(f"{_BASE}/marketdata/quotes/ZZZZ").mock(
            return_value=httpx.Response(
                404,
                json={"Message": "Symbol not found"},
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            with pytest.raises((ApiError, NotFoundError)):
                await svc.get_quotes(["ZZZZ"])

    @pytest.mark.asyncio
    @respx.mock
    async def test_network_error_raises_network_error(self) -> None:
        """Connection error propagates as NetworkError."""
        respx.get(f"{_BASE}/marketdata/quotes/AAPL").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            # disable retries for speed
            transport._retries = 0
            svc = MarketDataService(transport)
            with pytest.raises(NetworkError):
                await svc.get_quotes(["AAPL"])

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_quotes_list_returns_empty(self) -> None:
        """Empty Quotes array returns an empty list (not a crash)."""
        respx.get(f"{_BASE}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(
                200,
                json={"Quotes": []},
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            result = await svc.get_quotes(["AAPL"])

        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_unknown_fields_do_not_crash(self) -> None:
        """Extra/unknown fields in the quote dict are stored, not rejected."""
        quote_with_extra = dict(_CANNED_AAPL, FutureUnknownField="surprise")
        respx.get(f"{_BASE}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(
                200,
                json={"Quotes": [quote_with_extra]},
            )
        )
        async with httpx.AsyncClient() as http:
            transport = _make_transport(http)
            svc = MarketDataService(transport)
            quotes = await svc.get_quotes(["AAPL"])

        assert len(quotes) == 1
        assert quotes[0].symbol == "AAPL"
