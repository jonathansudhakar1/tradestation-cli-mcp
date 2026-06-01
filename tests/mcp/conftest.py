"""Shared test fixtures for the MCP test suite.

Provides:
    fake_client   — object with stubbed .market_data/.brokerage/.order_execution
    mcp_server    — pre-built FastMCP server wired to fake_client
    mcp_client    — in-process FastMCP Client connected to mcp_server
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastmcp import Client, FastMCP

# ---------------------------------------------------------------------------
# Fake service stubs
# ---------------------------------------------------------------------------

CANNED_QUOTES = [
    {"Symbol": "AAPL", "Last": 178.50, "Ask": 178.52, "Bid": 178.48},
    {"Symbol": "ES.M26", "Last": 5123.50, "Ask": 5123.75, "Bid": 5123.25},
    {"Symbol": "BTCUSD", "Last": 68000.00, "Ask": 68010.00, "Bid": 67990.00},
]

CANNED_BARS = [
    {"Open": 178.00, "High": 179.00, "Low": 177.50, "Close": 178.50, "Volume": 12345},
    {"Open": 178.50, "High": 179.50, "Low": 178.00, "Close": 179.00, "Volume": 23456},
]

CANNED_SYMBOLS = [
    {"Symbol": "AAPL", "Description": "Apple Inc.", "AssetType": "STOCK"},
    {"Symbol": "ES.M26", "Description": "E-mini S&P 500 Jun 26", "AssetType": "FUTURE"},
]

CANNED_ACCOUNTS = [
    {"AccountID": "11111111", "AccountType": "Margin", "Status": "Active"},
    {"AccountID": "22222222", "AccountType": "Cash", "Status": "Active"},
]

CANNED_BALANCES = [
    {"AccountID": "11111111", "CashBalance": 100000.00, "BuyingPower": 200000.00},
]

CANNED_POSITIONS = [
    {
        "AccountID": "11111111",
        "Symbol": "AAPL",
        "Quantity": 100,
        "AveragePrice": 175.00,
    },
    {
        "AccountID": "11111111",
        "Symbol": "ES.M26",
        "Quantity": 1,
        "AveragePrice": 5100.00,
    },
]

CANNED_ORDERS = [
    {
        "OrderID": "111111111",
        "AccountID": "11111111",
        "Symbol": "AAPL",
        "Quantity": 10,
        "Status": "Filled",
    }
]

CANNED_CONFIRM = {
    "OrderConfirmID": "CONF-001",
    "Route": "AUTO",
    "Duration": "DAY",
    "EstimatedCommission": "1.00",
    "EstimatedCost": "1785.00",
    "DebitCreditEstimatedCost": "-1785.00",
    "SummaryMessage": "Buy 10 AAPL @ Market",
}

CANNED_ACTIVATION_TRIGGERS = [
    {"Key": "STT", "Name": "Stop on Trade"},
    {"Key": "SST", "Name": "Stop on Spread Trade"},
]

CANNED_ROUTES = [
    {"Id": "AUTO", "Name": "Automatic Routing"},
    {"Id": "ARCX", "Name": "NYSE Arca"},
]

CANNED_WALLETS = [
    {"AccountID": "11111111", "Currency": "BTC", "Balance": 0.5},
]

CANNED_CRYPTO_PAIRS = [
    {"Name": "BTCUSD"},
    {"Name": "ETHUSD"},
]

CANNED_OPTION_EXPIRATIONS = [
    {"Date": "2026-06-20", "ExpirationStyle": "American"},
    {"Date": "2026-07-18", "ExpirationStyle": "American"},
]

CANNED_OPTION_STRIKES = [
    {"Strike": 170.0},
    {"Strike": 175.0},
    {"Strike": 180.0},
]

CANNED_SPREAD_TYPES = [
    {"Name": "Single"},
    {"Name": "Vertical"},
    {"Name": "Calendar"},
]

CANNED_RISK_REWARD = {
    "MaxGain": 200.00,
    "MaxLoss": -300.00,
    "BreakevenPoints": [177.50, 182.50],
}

CANNED_SYMBOL_LISTS = [
    {"SymbolListID": "list1", "Name": "My Watchlist"},
]

CANNED_PLACE_ORDER = {
    "OrderID": "987654321",
    "Status": "ACK",
    "Message": "Order received.",
}

CANNED_REPLACE_ORDER = {
    "OrderID": "987654321",
    "Status": "Replaced",
}

CANNED_CANCEL_ORDER = {
    "OrderID": "987654321",
    "Status": "Cancelled",
}


class FakeMarketDataService:
    """Fake MarketData service returning canned data."""

    async def get_quotes(self, symbols: list[str]) -> list[dict]:
        return [q for q in CANNED_QUOTES if q["Symbol"] in symbols] or CANNED_QUOTES

    async def get_bars(self, symbol: str, **kwargs: object) -> list[dict]:
        return CANNED_BARS

    async def get_symbols(self, symbols: list[str]) -> list[dict]:
        return CANNED_SYMBOLS

    async def list_symbol_lists(self) -> list[dict]:
        return CANNED_SYMBOL_LISTS

    async def get_symbol_list(self, list_id: str) -> dict:
        return {"SymbolListID": list_id, "Name": "My List"}

    async def get_symbol_list_symbols(self, list_id: str) -> list[dict]:
        return [{"Symbol": "AAPL"}, {"Symbol": "MSFT"}]

    async def list_crypto_pairs(self) -> list[dict]:
        return CANNED_CRYPTO_PAIRS

    async def get_option_expirations(self, underlying: str, **kwargs: object) -> list[dict]:
        return CANNED_OPTION_EXPIRATIONS

    async def get_option_strikes(self, underlying: str, **kwargs: object) -> list[dict]:
        return CANNED_OPTION_STRIKES

    async def list_option_spread_types(self) -> list[dict]:
        return CANNED_SPREAD_TYPES

    async def option_risk_reward(self, legs: list[dict], *, entry: float) -> dict:
        return CANNED_RISK_REWARD

    async def stream_bars(self, symbol: str, **kwargs: object) -> list[dict]:
        return CANNED_BARS

    async def stream_quotes(self, symbols: list[str]) -> list[dict]:
        return CANNED_QUOTES[:2]

    async def stream_depth_quotes(self, symbol: str) -> list[dict]:
        return [{"Symbol": symbol, "Bid": 178.48, "Ask": 178.52}]

    async def stream_depth_aggregates(self, symbol: str) -> list[dict]:
        return [{"Symbol": symbol, "Bids": [], "Asks": []}]

    async def stream_option_chain(self, underlying: str, expiration: str) -> list[dict]:
        return [{"Underlying": underlying, "Expiration": expiration}]

    async def stream_option_quotes(self, legs: list[dict]) -> list[dict]:
        return [{"Leg": legs[0] if legs else {}}]


class FakeBrokerageService:
    """Fake Brokerage service returning canned data."""

    async def list_accounts(self) -> list[dict]:
        return CANNED_ACCOUNTS

    async def get_balances(self, account_ids: list[str]) -> list[dict]:
        return CANNED_BALANCES

    async def get_bod_balances(self, account_ids: list[str]) -> list[dict]:
        return CANNED_BALANCES

    async def get_positions(self, account_ids: list[str]) -> list[dict]:
        return CANNED_POSITIONS

    async def get_orders(self, account_ids: list[str]) -> list[dict]:
        return CANNED_ORDERS

    async def get_orders_by_id(self, account_ids: list[str], order_ids: list[str]) -> list[dict]:
        return [o for o in CANNED_ORDERS if o["OrderID"] in order_ids] or CANNED_ORDERS

    async def get_historical_orders(self, account_ids: list[str], since: object) -> list[dict]:
        return CANNED_ORDERS

    async def get_historical_orders_by_id(
        self, account_ids: list[str], order_ids: list[str]
    ) -> list[dict]:
        return CANNED_ORDERS

    async def get_wallets(self, account_ids: list[str]) -> list[dict]:
        return CANNED_WALLETS

    async def stream_orders(self, account_ids: list[str]) -> list[dict]:
        return CANNED_ORDERS[:1]

    async def stream_orders_by_id(self, account_ids: list[str], order_ids: list[str]) -> list[dict]:
        return CANNED_ORDERS[:1]

    async def stream_positions(self, account_ids: list[str]) -> list[dict]:
        return CANNED_POSITIONS[:1]

    async def stream_wallets(self, account_ids: list[str]) -> list[dict]:
        return CANNED_WALLETS


class FakeOrderExecutionService:
    """Fake OrderExecution service returning canned data."""

    async def confirm_order(self, request: object) -> dict:
        return CANNED_CONFIRM

    async def place_order(self, request: object) -> dict:
        return CANNED_PLACE_ORDER

    async def replace_order(self, order_id: str, request: object) -> dict:
        return CANNED_REPLACE_ORDER

    async def cancel_order(self, order_id: str) -> dict:
        return CANNED_CANCEL_ORDER

    async def confirm_order_group(self, request: object) -> dict:
        return {**CANNED_CONFIRM, "OrderConfirmID": "GRPCONF-001"}

    async def place_order_group(self, request: object) -> dict:
        return {**CANNED_PLACE_ORDER, "OrderID": "GROUP-001"}

    async def list_activation_triggers(self) -> list[dict]:
        return CANNED_ACTIVATION_TRIGGERS

    async def list_routes(self) -> list[dict]:
        return CANNED_ROUTES


class FakeTradeStationClient:
    """Minimal fake TradeStationClient for MCP tests."""

    def __init__(self) -> None:
        self.market_data: FakeMarketDataService = FakeMarketDataService()
        self.brokerage: FakeBrokerageService = FakeBrokerageService()
        self.order_execution: FakeOrderExecutionService = FakeOrderExecutionService()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_client() -> FakeTradeStationClient:
    """Return a fresh FakeTradeStationClient for each test."""
    return FakeTradeStationClient()


@pytest.fixture
def mcp_server(fake_client: FakeTradeStationClient) -> FastMCP:
    """Return a fully-configured FastMCP server wired to the fake client."""
    from tradestation.mcp.server import build_server

    return build_server(
        toolsets="all",
        read_only=False,
        confirm_mode="require",
        client=fake_client,
    )


@pytest_asyncio.fixture
async def mcp_client(mcp_server: FastMCP) -> Client:  # type: ignore[misc]
    """Return an in-process FastMCP Client connected to mcp_server."""
    async with Client(mcp_server) as c:
        yield c
