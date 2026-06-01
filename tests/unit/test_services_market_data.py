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


# ---------------------------------------------------------------------------
# B1 — get_bars
# ---------------------------------------------------------------------------

_CANNED_BARS = {
    "Bars": [
        {
            "Open": "177.10", "High": "178.20", "Low": "176.90", "Close": "178.05",
            "TimeStamp": "2026-06-01T13:30:00Z", "TotalVolume": "1200000",
            "TotalTrades": "8500", "IsRealtime": False, "IsEndOfHistory": False,
        },
        {
            "Open": "178.05", "High": "179.02", "Low": "177.80", "Close": "178.45",
            "TimeStamp": "2026-06-01T13:31:00Z", "TotalVolume": "980000",
            "TotalTrades": "7200", "IsRealtime": False, "IsEndOfHistory": True,
        },
    ]
}


class TestGetBars:
    @pytest.mark.asyncio
    @respx.mock
    async def test_bars_basic(self) -> None:
        route = respx.get(f"{_BASE}/marketdata/barcharts/AAPL").mock(
            return_value=httpx.Response(200, json=_CANNED_BARS)
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            bars = await svc.get_bars("AAPL", barsback=2)

        assert route.called
        params = route.calls.last.request.url.params
        assert params["interval"] == "1"
        assert params["unit"] == "Minute"
        assert params["barsback"] == "2"
        assert params["sessiontemplate"] == "Default"
        assert len(bars) == 2
        assert bars[0].open == pytest.approx(177.10)
        assert bars[0].close == pytest.approx(178.05)
        assert bars[0].total_volume == 1200000
        assert bars[1].is_end_of_history is True
        assert bars[0].datetime_utc is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_bars_daily_with_dates(self) -> None:
        route = respx.get(f"{_BASE}/marketdata/barcharts/ESM26").mock(
            return_value=httpx.Response(200, json={"Bars": []})
        )
        from tradestation.enums import BarUnit, MarketSession

        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            await svc.get_bars(
                "ESM26",
                interval=1,
                unit=BarUnit.DAILY,
                firstdate="2026-05-01",
                lastdate="2026-05-31",
                session_template=MarketSession.EXTENDED_HOURS,
            )
        params = route.calls.last.request.url.params
        assert params["unit"] == "Daily"
        assert params["firstdate"] == "2026-05-01"
        assert params["lastdate"] == "2026-05-31"
        assert params["sessiontemplate"] == "USEQPreAndPost"

    @pytest.mark.asyncio
    @respx.mock
    async def test_bars_empty(self) -> None:
        respx.get(f"{_BASE}/marketdata/barcharts/BTCUSD").mock(
            return_value=httpx.Response(200, json={"Bars": []})
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            assert await svc.get_bars("BTCUSD") == []


# ---------------------------------------------------------------------------
# B3-B11 — symbols, lists, crypto, options
# ---------------------------------------------------------------------------


class TestSymbolsAndLists:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_symbols(self) -> None:
        respx.get(f"{_BASE}/marketdata/symbols/AAPL,ESM26").mock(
            return_value=httpx.Response(
                200,
                json={"Symbols": [
                    {"Symbol": "AAPL", "AssetType": "STOCK", "Exchange": "NASDAQ",
                     "Currency": "USD"},
                    {"Symbol": "ESM26", "AssetType": "FUTURE", "Root": "ES",
                     "Currency": "USD"},
                ], "Errors": []},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            syms = await svc.get_symbols(["AAPL", "ESM26"])
        assert len(syms) == 2
        assert syms[1].asset_type == "FUTURE"
        assert syms[1].root == "ES"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_symbol_lists(self) -> None:
        respx.get(f"{_BASE}/marketdata/symbollists").mock(
            return_value=httpx.Response(
                200,
                json={"SymbolLists": [
                    {"SymbolListID": "abc", "Name": "Faves", "Count": 12},
                ]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            lists = await svc.list_symbol_lists()
        assert lists[0].symbol_list_id == "abc"
        assert lists[0].count == 12

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_symbol_list(self) -> None:
        respx.get(f"{_BASE}/marketdata/symbollists/abc").mock(
            return_value=httpx.Response(200, json={"SymbolListID": "abc", "Name": "Faves"})
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            sl = await svc.get_symbol_list("abc")
        assert sl is not None
        assert sl.name == "Faves"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_symbol_list_symbols(self) -> None:
        respx.get(f"{_BASE}/marketdata/symbollists/abc/symbols").mock(
            return_value=httpx.Response(
                200, json={"Symbols": [{"Symbol": "AAPL"}, {"Symbol": "MSFT"}]}
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            syms = await svc.get_symbol_list_symbols("abc")
        assert [s.symbol for s in syms] == ["AAPL", "MSFT"]


class TestCrypto:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_crypto_pairs(self) -> None:
        respx.get(f"{_BASE}/marketdata/crypto/symbolnames").mock(
            return_value=httpx.Response(
                200, json={"SymbolNames": ["BTCUSD", "ETHUSD", "LTCUSD"]}
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            pairs = await svc.list_crypto_pairs()
        assert "BTCUSD" in pairs
        assert len(pairs) == 3


class TestOptions:
    @pytest.mark.asyncio
    @respx.mock
    async def test_option_expirations(self) -> None:
        route = respx.get(f"{_BASE}/marketdata/options/expirations/AAPL").mock(
            return_value=httpx.Response(
                200,
                json={"Expirations": [
                    {"Date": "2026-06-19T00:00:00Z", "Type": "Monthly"},
                    {"Date": "2026-06-26T00:00:00Z", "Type": "Weekly"},
                ]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            exps = await svc.get_option_expirations("AAPL", strike=200)
        assert route.calls.last.request.url.params["strikePrice"] == "200"
        assert len(exps) == 2
        assert exps[0].type == "Monthly"

    @pytest.mark.asyncio
    @respx.mock
    async def test_option_strikes(self) -> None:
        route = respx.get(f"{_BASE}/marketdata/options/strikes/AAPL").mock(
            return_value=httpx.Response(
                200,
                json={"SpreadType": "Single", "Strikes": [["190"], ["195"], ["200"]]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            res = await svc.get_option_strikes(
                "AAPL", expiration="2026-06-19", spread_type="Single"
            )
        assert route.calls.last.request.url.params["expiration"] == "2026-06-19"
        assert res["SpreadType"] == "Single"
        assert len(res["Strikes"]) == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_option_spread_types(self) -> None:
        respx.get(f"{_BASE}/marketdata/options/spreadtypes").mock(
            return_value=httpx.Response(
                200,
                json={"SpreadTypes": [
                    {"Name": "Single", "StrikeInterval": False, "ExpirationInterval": False},
                    {"Name": "Vertical", "StrikeInterval": True, "ExpirationInterval": False},
                ]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            types = await svc.list_option_spread_types()
        assert [t.name for t in types] == ["Single", "Vertical"]
        assert types[1].strike_interval is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_option_risk_reward(self) -> None:
        route = respx.post(f"{_BASE}/marketdata/options/riskreward").mock(
            return_value=httpx.Response(
                200,
                json={"MaxGain": "330", "MaxLoss": "170", "RiskRewardRatio": "1.94",
                      "Commission": "0"},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = MarketDataService(_make_transport(http))
            res = await svc.option_risk_reward(
                [{"Symbol": "AAPL 260620C200", "Ratio": 1, "OpenPrice": "5.40"},
                 {"Symbol": "AAPL 260620C210", "Ratio": -1, "OpenPrice": "2.10"}],
                entry=3.30,
            )
        assert route.called
        import json as _json
        body = _json.loads(route.calls.last.request.content)
        assert body["SpreadPrice"] == "3.3"
        assert len(body["Legs"]) == 2
        assert res["MaxGain"] == "330"
