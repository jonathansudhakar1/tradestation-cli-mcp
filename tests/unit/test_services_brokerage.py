"""Unit tests for BrokerageService (C1-C9).

Uses respx to mock HTTP; no real network calls.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from tradestation.credentials import Credentials
from tradestation.enums import Environment
from tradestation.errors import ApiError
from tradestation.models.brokerage import (
    Account,
    Balances,
    Order,
    Position,
    Wallet,
)
from tradestation.services.brokerage import BrokerageService
from tradestation.transport import Transport

_BASE = "https://sim-api.tradestation.com/v3"


def _make_transport(http_client: httpx.AsyncClient) -> Transport:
    creds = Credentials(
        client_id="FAKE",
        client_secret="FAKE",
        refresh_token="FAKE",
        environment=Environment.SIM,
        access_token="FAKE_TOKEN",
        access_token_expires_at="2099-01-01T00:00:00Z",
    )
    return Transport(creds, http_client=http_client)


async def _svc(http: httpx.AsyncClient) -> BrokerageService:
    return BrokerageService(_make_transport(http))


# ---------------------------------------------------------------------------
# C1 — accounts
# ---------------------------------------------------------------------------


class TestListAccounts:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_accounts(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Accounts": [
                        {"AccountID": "11111111", "AccountType": "Margin",
                         "Currency": "USD", "Status": "Active"},
                        {"AccountID": "22222222", "AccountType": "Cash",
                         "Currency": "USD", "Status": "Active"},
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            accounts = await svc.list_accounts()

        assert len(accounts) == 2
        assert all(isinstance(a, Account) for a in accounts)
        assert accounts[0].account_id == "11111111"
        assert accounts[0].account_type == "Margin"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_accounts(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts").mock(
            return_value=httpx.Response(200, json={"Accounts": []})
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            assert await svc.list_accounts() == []


# ---------------------------------------------------------------------------
# C2 / C3 — balances
# ---------------------------------------------------------------------------


class TestBalances:
    @pytest.mark.asyncio
    @respx.mock
    async def test_balances_single_account(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts/11111111/balances").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Balances": [
                        {
                            "AccountID": "11111111",
                            "AccountType": "Margin",
                            "CashBalance": "5002.11",
                            "Equity": "124308.41",
                            "BuyingPower": "248616.82",
                            "MarketValue": "119306.30",
                            "BalanceDetail": {"RequiredMargin": "0", "DayTrades": "0"},
                        }
                    ],
                    "Errors": [],
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            balances = await svc.get_balances(["11111111"])

        assert len(balances) == 1
        b = balances[0]
        assert isinstance(b, Balances)
        assert b.account_id == "11111111"
        assert b.equity == pytest.approx(124308.41)
        assert b.buying_power == pytest.approx(248616.82)
        assert b.balance_detail is not None
        assert b.balance_detail.required_margin == pytest.approx(0.0)

    @pytest.mark.asyncio
    @respx.mock
    async def test_balances_multi_account_csv_path(self) -> None:
        route = respx.get(f"{_BASE}/brokerage/accounts/11111111,22222222/balances").mock(
            return_value=httpx.Response(200, json={"Balances": []})
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            await svc.get_balances(["11111111", "22222222"])
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_bod_balances(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts/11111111/bodbalances").mock(
            return_value=httpx.Response(
                200,
                json={"BODBalances": [{"AccountID": "11111111", "Equity": "120000.00"}]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            bod = await svc.get_bod_balances(["11111111"])
        assert len(bod) == 1
        assert bod[0].equity == pytest.approx(120000.00)


# ---------------------------------------------------------------------------
# C4 — positions (incl. futures + crypto)
# ---------------------------------------------------------------------------


class TestPositions:
    @pytest.mark.asyncio
    @respx.mock
    async def test_positions_equity_future_crypto(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts/11111111/positions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Positions": [
                        {"AccountID": "11111111", "Symbol": "AAPL", "AssetType": "STOCK",
                         "Quantity": "500", "LongShort": "Long", "AveragePrice": "162.10",
                         "Last": "178.45", "MarketValue": "89225.00",
                         "UnrealizedProfitLoss": "8175.00",
                         "UnrealizedProfitLossPercent": "10.09"},
                        {"AccountID": "11111111", "Symbol": "ESM26", "AssetType": "FUTURE",
                         "Quantity": "2", "LongShort": "Long", "AveragePrice": "5300.00",
                         "Last": "5318.50", "MarketValue": "531850.00",
                         "UnrealizedProfitLoss": "1850.00"},
                        {"AccountID": "11111111", "Symbol": "BTCUSD", "AssetType": "CRYPTO",
                         "Quantity": "0.5", "LongShort": "Long", "AveragePrice": "68000.00",
                         "Last": "71200.00", "MarketValue": "35600.00",
                         "UnrealizedProfitLoss": "1600.00"},
                    ],
                    "Errors": [],
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            positions = await svc.get_positions(["11111111"])

        assert len(positions) == 3
        assert all(isinstance(p, Position) for p in positions)
        fut = next(p for p in positions if p.symbol == "ESM26")
        assert fut.asset_type == "FUTURE"
        assert fut.quantity == pytest.approx(2.0)
        crypto = next(p for p in positions if p.symbol == "BTCUSD")
        assert crypto.quantity == pytest.approx(0.5)  # fractional qty


# ---------------------------------------------------------------------------
# C5 / C6 — orders
# ---------------------------------------------------------------------------


class TestOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_orders(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts/11111111/orders").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Orders": [
                        {"AccountID": "11111111", "OrderID": "835711", "Status": "OPN",
                         "StatusDescription": "Sent", "OrderType": "Limit",
                         "Symbol": "AAPL", "Quantity": "100", "FilledQuantity": "0",
                         "LimitPrice": "178.00", "Duration": "DAY"},
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            orders = await svc.get_orders(["11111111"])
        assert len(orders) == 1
        assert isinstance(orders[0], Order)
        assert orders[0].order_id == "835711"
        assert orders[0].limit_price == pytest.approx(178.00)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_orders_by_id_path(self) -> None:
        route = respx.get(
            f"{_BASE}/brokerage/accounts/11111111/orders/835711,835712"
        ).mock(return_value=httpx.Response(200, json={"Orders": []}))
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            await svc.get_orders_by_id(["11111111"], ["835711", "835712"])
        assert route.called


# ---------------------------------------------------------------------------
# C7 / C8 — historical orders
# ---------------------------------------------------------------------------


class TestHistoricalOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_historical_orders_since_param(self) -> None:
        route = respx.get(
            f"{_BASE}/brokerage/accounts/11111111/historicalorders"
        ).mock(return_value=httpx.Response(200, json={"Orders": []}))
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            await svc.get_historical_orders(["11111111"], since=date(2026, 1, 1))
        assert route.called
        assert route.calls.last.request.url.params["since"] == "2026-01-01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_historical_orders_by_id(self) -> None:
        route = respx.get(
            f"{_BASE}/brokerage/accounts/11111111/historicalorders/835711"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"Orders": [{"OrderID": "835711", "Status": "FLL",
                                  "Symbol": "AAPL", "FilledPrice": "178.01"}]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            orders = await svc.get_historical_orders_by_id(["11111111"], ["835711"])
        assert route.called
        assert orders[0].filled_price == pytest.approx(178.01)


# ---------------------------------------------------------------------------
# C9 — wallets
# ---------------------------------------------------------------------------


class TestWallets:
    @pytest.mark.asyncio
    @respx.mock
    async def test_wallets(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts/11111111/wallets").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Wallets": [
                        {"AccountID": "11111111", "Currency": "BTC",
                         "Balance": "0.5", "AvailableBalance": "0.5"},
                        {"AccountID": "11111111", "Currency": "USD",
                         "Balance": "5000.00", "AvailableBalance": "5000.00"},
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            wallets = await svc.get_wallets(["11111111"])
        assert len(wallets) == 2
        assert all(isinstance(w, Wallet) for w in wallets)
        btc = next(w for w in wallets if w.currency == "BTC")
        assert btc.balance == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestErrors:
    @pytest.mark.asyncio
    @respx.mock
    async def test_api_error_propagates(self) -> None:
        respx.get(f"{_BASE}/brokerage/accounts").mock(
            return_value=httpx.Response(500, json={"Error": "ServerError",
                                                    "Message": "boom"})
        )
        async with httpx.AsyncClient() as http:
            svc = await _svc(http)
            with pytest.raises(ApiError):
                await svc.list_accounts()
