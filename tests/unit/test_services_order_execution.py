"""Unit tests for OrderExecutionService (D1-D8).

Uses respx to mock HTTP; NO live order placement. Destructive endpoints
(D2/D3/D4/D6) are exercised against mocks only.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from tradestation.credentials import Credentials
from tradestation.enums import OrderType, Side, TimeInForce
from tradestation.models.orders import (
    LimitOrderRequest,
    MarketOrderRequest,
    OrderGroupRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)
from tradestation.services.order_execution import OrderExecutionService
from tradestation.transport import Transport

_BASE = "https://sim-api.tradestation.com/v3"


def _svc(http: httpx.AsyncClient) -> OrderExecutionService:
    creds = Credentials(
        client_id="FAKE",
        client_secret="FAKE",
        refresh_token="FAKE",
        access_token="FAKE_TOKEN",
        access_token_expires_at="2099-01-01T00:00:00Z",
    )
    return OrderExecutionService(Transport(creds, http_client=http))


# ---------------------------------------------------------------------------
# Request model serialisation
# ---------------------------------------------------------------------------


class TestRequestSerialisation:
    def test_market_order_body(self) -> None:
        req = MarketOrderRequest(account_id="11111111", symbol="AAPL", quantity=100, side=Side.BUY)
        body = req.to_api()
        assert body["AccountID"] == "11111111"
        assert body["Symbol"] == "AAPL"
        assert body["Quantity"] == "100"
        assert body["OrderType"] == "Market"
        assert body["TradeAction"] == "BUY"
        assert body["TimeInForce"] == {"Duration": "DAY"}
        assert "LimitPrice" not in body

    def test_limit_order_body(self) -> None:
        req = LimitOrderRequest(
            account_id="11111111",
            symbol="AAPL",
            quantity=100,
            side=Side.SELL,
            limit_price=190.50,
        )
        body = req.to_api()
        assert body["OrderType"] == "Limit"
        assert body["TradeAction"] == "SELL"
        assert body["LimitPrice"] == "190.5"

    def test_stop_limit_body(self) -> None:
        req = StopLimitOrderRequest(
            account_id="1",
            symbol="AAPL",
            quantity=10,
            side=Side.SELL_SHORT,
            stop_price=170.0,
            limit_price=169.0,
        )
        body = req.to_api()
        assert body["OrderType"] == "StopLimit"
        assert body["TradeAction"] == "SELLSHORT"
        assert body["StopPrice"] == "170.0"
        assert body["LimitPrice"] == "169.0"

    def test_stop_market_body(self) -> None:
        req = StopOrderRequest(
            account_id="1", symbol="ESM26", quantity=1, side=Side.BUY, stop_price=5400.0
        )
        body = req.to_api()
        assert body["OrderType"] == "StopMarket"
        assert body["StopPrice"] == "5400.0"

    def test_gtd_expiration(self) -> None:
        req = MarketOrderRequest(
            account_id="1",
            symbol="AAPL",
            quantity=1,
            side=Side.BUY,
            time_in_force=TimeInForce.GTD,
            gtd_expiration="2026-12-31",
        )
        body = req.to_api()
        assert body["TimeInForce"] == {"Duration": "GTD", "Expiration": "2026-12-31"}

    def test_frozen_order_type(self) -> None:
        # The discriminator is frozen — a market request stays Market.
        req = MarketOrderRequest(account_id="1", symbol="AAPL", quantity=1, side=Side.BUY)
        assert req.order_type is OrderType.MARKET


# ---------------------------------------------------------------------------
# D1 — confirm (safe)
# ---------------------------------------------------------------------------


class TestConfirmOrder:
    @pytest.mark.asyncio
    @respx.mock
    async def test_confirm(self) -> None:
        route = respx.post(f"{_BASE}/orderexecution/orderconfirm").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Confirmations": [
                        {
                            "AccountID": "11111111",
                            "Symbol": "AAPL",
                            "Quantity": "100",
                            "OrderType": "Market",
                            "EstimatedCost": "16743.00",
                            "EstimatedCommission": "0",
                            "Route": "Intelligent",
                            "SummaryMessage": "Buy 100 AAPL @ Market",
                        },
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            confs = await svc.confirm_order(
                MarketOrderRequest(
                    account_id="11111111", symbol="AAPL", quantity=100, side=Side.BUY
                )
            )
        assert route.called
        body = json.loads(route.calls.last.request.content)
        assert body["TradeAction"] == "BUY"
        assert len(confs) == 1
        assert confs[0].estimated_cost == "16743.00"


# ---------------------------------------------------------------------------
# D2 / D3 / D4 — place / replace / cancel (mocked only — never live)
# ---------------------------------------------------------------------------


class TestPlaceReplaceCancel:
    @pytest.mark.asyncio
    @respx.mock
    async def test_place_order(self) -> None:
        respx.post(f"{_BASE}/orderexecution/orders").mock(
            return_value=httpx.Response(
                200,
                json={"Orders": [{"OrderID": "835711", "Message": "Sent"}]},
            )
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            resp = await svc.place_order(
                LimitOrderRequest(
                    account_id="1", symbol="AAPL", quantity=100, side=Side.BUY, limit_price=178.0
                )
            )
        assert resp.orders[0].order_id == "835711"
        assert resp.rejected is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_place_order_rejected(self) -> None:
        respx.post(f"{_BASE}/orderexecution/orders").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Orders": [
                        {
                            "OrderID": "0",
                            "Error": "InsufficientFunds",
                            "Message": "Not enough buying power",
                        }
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            resp = await svc.place_order(
                MarketOrderRequest(account_id="1", symbol="AAPL", quantity=1e9, side=Side.BUY)
            )
        assert resp.rejected is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_replace_order_uses_put(self) -> None:
        route = respx.put(f"{_BASE}/orderexecution/orders/835711").mock(
            return_value=httpx.Response(200, json={"Orders": [{"OrderID": "835711"}]})
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            await svc.replace_order(
                "835711",
                LimitOrderRequest(
                    account_id="1", symbol="AAPL", quantity=100, side=Side.BUY, limit_price=179.0
                ),
            )
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_cancel_order_uses_delete(self) -> None:
        route = respx.delete(f"{_BASE}/orderexecution/orders/835711").mock(
            return_value=httpx.Response(200, json={"Orders": [{"OrderID": "835711"}]})
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            await svc.cancel_order("835711")
        assert route.called


# ---------------------------------------------------------------------------
# D5 / D6 — order groups
# ---------------------------------------------------------------------------


class TestOrderGroups:
    def test_group_body(self) -> None:
        grp = OrderGroupRequest(
            group_type="OCO",
            orders=[
                LimitOrderRequest(
                    account_id="1", symbol="AAPL", quantity=100, side=Side.SELL, limit_price=190.0
                ),
                StopOrderRequest(
                    account_id="1", symbol="AAPL", quantity=100, side=Side.SELL, stop_price=170.0
                ),
            ],
        )
        body = grp.to_api()
        assert body["Type"] == "OCO"
        assert len(body["Orders"]) == 2
        assert body["Orders"][0]["OrderType"] == "Limit"
        assert body["Orders"][1]["OrderType"] == "StopMarket"

    @pytest.mark.asyncio
    @respx.mock
    async def test_confirm_group(self) -> None:
        respx.post(f"{_BASE}/orderexecution/ordergroupconfirm").mock(
            return_value=httpx.Response(
                200, json={"Confirmations": [{"Symbol": "AAPL"}, {"Symbol": "AAPL"}]}
            )
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            grp = OrderGroupRequest(
                group_type="OCO",
                orders=[
                    LimitOrderRequest(
                        account_id="1",
                        symbol="AAPL",
                        quantity=100,
                        side=Side.SELL,
                        limit_price=190.0,
                    ),
                    StopOrderRequest(
                        account_id="1",
                        symbol="AAPL",
                        quantity=100,
                        side=Side.SELL,
                        stop_price=170.0,
                    ),
                ],
            )
            confs = await svc.confirm_order_group(grp)
        assert len(confs) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_place_group(self) -> None:
        respx.post(f"{_BASE}/orderexecution/ordergroups").mock(
            return_value=httpx.Response(200, json={"Orders": [{"OrderID": "1"}, {"OrderID": "2"}]})
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            grp = OrderGroupRequest(
                group_type="BRK",
                orders=[
                    MarketOrderRequest(account_id="1", symbol="AAPL", quantity=100, side=Side.BUY),
                ],
            )
            resp = await svc.place_order_group(grp)
        assert len(resp.orders) == 2


# ---------------------------------------------------------------------------
# D7 / D8 — triggers + routes (safe read-only)
# ---------------------------------------------------------------------------


class TestTriggersAndRoutes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_activation_triggers(self) -> None:
        respx.get(f"{_BASE}/orderexecution/activationtriggers").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ActivationTriggers": [
                        {
                            "Key": "STT",
                            "Name": "SingleTradeTick",
                            "Description": "Trigger on a single trade tick",
                        },
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            triggers = await svc.list_activation_triggers()
        assert triggers[0].key == "STT"

    @pytest.mark.asyncio
    @respx.mock
    async def test_routes(self) -> None:
        respx.get(f"{_BASE}/orderexecution/routes").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Routes": [
                        {"Id": "AUTO", "Name": "Intelligent", "AssetTypes": ["STOCK"]},
                        {"Id": "ARCA", "Name": "ARCA", "AssetTypes": ["STOCK"]},
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            svc = _svc(http)
            routes = await svc.list_routes()
        assert [r.id for r in routes] == ["AUTO", "ARCA"]
