"""Live integration tests against the TradeStation SIM API.

These hit sim-api.tradestation.com using the credentials in ``.env``. They are
marked ``@pytest.mark.live`` and skipped by default; run with::

    pytest -m live tests/integration/test_live_endpoints.py -v

Only READ-ONLY endpoints and order *previews* (orderconfirm) are exercised —
no orders are ever submitted, replaced, or cancelled.
"""

from __future__ import annotations

import pytest

from tradestation.client import TradeStationClient
from tradestation.enums import Side
from tradestation.models.orders import MarketOrderRequest

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


@pytest.fixture
async def client(_load_dotenv_for_live_tests: None) -> TradeStationClient:
    """A sim client built from the .env credentials."""
    return TradeStationClient.from_env()


@pytest.fixture
async def accounts(client: TradeStationClient) -> list:
    accts = await client.brokerage.list_accounts()
    assert accts, "expected at least one sim account"
    return accts


def _by_type(accounts: list, type_substr: str) -> str | None:
    for a in accounts:
        if a.account_type and type_substr.lower() in a.account_type.lower():
            return a.account_id
    return None


# ---------------------------------------------------------------------------
# Brokerage (C1-C9)
# ---------------------------------------------------------------------------


class TestBrokerageLive:
    async def test_accounts(self, accounts: list) -> None:
        for a in accounts:
            assert a.account_id
            assert a.account_type
        print("\nAccounts:", [(a.account_id, a.account_type) for a in accounts])

    async def test_balances(self, client: TradeStationClient, accounts: list) -> None:
        acct = accounts[0].account_id
        balances = await client.brokerage.get_balances([acct])
        assert balances
        b = balances[0]
        assert b.account_id == acct
        print(f"\nBalance {acct}: equity={b.equity} buying_power={b.buying_power}")

    async def test_bod_balances(self, client: TradeStationClient, accounts: list) -> None:
        acct = accounts[0].account_id
        bod = await client.brokerage.get_bod_balances([acct])
        assert isinstance(bod, list)

    async def test_positions(self, client: TradeStationClient, accounts: list) -> None:
        acct = _by_type(accounts, "Margin") or accounts[0].account_id
        positions = await client.brokerage.get_positions([acct])
        for p in positions:
            assert p.symbol
        print(f"\nPositions {acct}: {[(p.symbol, p.quantity) for p in positions]}")

    async def test_orders(self, client: TradeStationClient, accounts: list) -> None:
        acct = accounts[0].account_id
        orders = await client.brokerage.get_orders([acct])
        assert isinstance(orders, list)
        for o in orders:
            assert o.order_id

    async def test_wallets(self, client: TradeStationClient, accounts: list) -> None:
        fut = _by_type(accounts, "Futures") or accounts[0].account_id
        wallets = await client.brokerage.get_wallets([fut])
        assert isinstance(wallets, list)
        print(f"\nWallets {fut}: {[(w.currency, w.balance) for w in wallets[:5]]}")


# ---------------------------------------------------------------------------
# Market data (B1-B11)
# ---------------------------------------------------------------------------


class TestMarketDataLive:
    async def test_quotes_equity_crypto(self, client: TradeStationClient) -> None:
        quotes = await client.market_data.get_quotes(["AAPL", "MSFT", "BTCUSD"])
        assert quotes
        for q in quotes:
            assert q.symbol
        aapl = next(q for q in quotes if q.symbol == "AAPL")
        assert aapl.last and aapl.last > 0
        print(f"\nAAPL last={aapl.last}")

    async def test_bars(self, client: TradeStationClient) -> None:
        bars = await client.market_data.get_bars("AAPL", barsback=10)
        assert len(bars) == 10
        assert bars[0].close and bars[0].close > 0
        assert bars[0].datetime_utc is not None

    async def test_bars_futures(self, client: TradeStationClient) -> None:
        # Continuous front-month S&P E-mini future.
        bars = await client.market_data.get_bars("@ES", barsback=5)
        assert isinstance(bars, list)

    async def test_symbols(self, client: TradeStationClient) -> None:
        syms = await client.market_data.get_symbols(["AAPL"])
        assert syms
        assert syms[0].asset_type

    async def test_crypto_pairs(self, client: TradeStationClient) -> None:
        pairs = await client.market_data.list_crypto_pairs()
        assert "BTCUSD" in pairs

    async def test_option_expirations(self, client: TradeStationClient) -> None:
        exps = await client.market_data.get_option_expirations("AAPL")
        assert exps
        assert exps[0].date

    async def test_option_strikes(self, client: TradeStationClient) -> None:
        exps = await client.market_data.get_option_expirations("AAPL")
        exp_date = exps[0].date
        strikes = await client.market_data.get_option_strikes("AAPL", expiration=exp_date)
        assert "Strikes" in strikes

    async def test_option_spread_types(self, client: TradeStationClient) -> None:
        types = await client.market_data.list_option_spread_types()
        assert any(t.name == "Single" for t in types)


# ---------------------------------------------------------------------------
# Order execution — SAFE only (routes, triggers, confirm preview)
# ---------------------------------------------------------------------------


class TestOrderExecutionLive:
    async def test_routes(self, client: TradeStationClient) -> None:
        routes = await client.order_execution.list_routes()
        assert routes
        assert any(r.name for r in routes)

    async def test_activation_triggers(self, client: TradeStationClient) -> None:
        triggers = await client.order_execution.list_activation_triggers()
        assert triggers
        assert any(t.key for t in triggers)

    async def test_confirm_order_preview_only(
        self, client: TradeStationClient, accounts: list
    ) -> None:
        """D1 preview — NEVER submits. Validates OrderConfirmation against live."""
        acct = _by_type(accounts, "Margin") or accounts[0].account_id
        req = MarketOrderRequest(
            account_id=acct, symbol="AAPL", quantity=1, side=Side.BUY
        )
        confs = await client.order_execution.confirm_order(req)
        assert confs, "expected a confirmation preview"
        print(f"\nConfirm preview: {confs[0].model_dump(exclude_none=True)}")
