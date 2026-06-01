"""Brokerage Pydantic models (C-series endpoints).

Covers the C1-C9 response shapes:
- C1 GET /v3/brokerage/accounts
- C2 GET /v3/brokerage/accounts/{ids}/balances
- C3 GET /v3/brokerage/accounts/{ids}/balances/bod
- C4 GET /v3/brokerage/accounts/{ids}/positions
- C5 GET /v3/brokerage/accounts/{ids}/orders
- C6 GET /v3/brokerage/accounts/{ids}/orders/{orderIds}
- C7 GET /v3/brokerage/accounts/{ids}/historicalorders
- C8 GET /v3/brokerage/accounts/{ids}/historicalorders/{orderIds}
- C9 GET /v3/brokerage/accounts/{ids}/wallets

v3 reality (consistent with the quotes endpoint):
- List responses are envelopes: ``{"Accounts": [...]}``, ``{"Balances": [...], "Errors": [...]}``,
  ``{"Positions": [...]}``, ``{"Orders": [...]}``, ``{"Wallets": [...]}``.
- Numeric fields arrive as strings; Pydantic v2 lax mode coerces them.
- Empty strings are coerced to ``None`` by the shared before-validator.
- Unknown fields are preserved via ``extra="allow"``.

See docs/05-python-library.md §"Models".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _TSModel(BaseModel):
    """Base for all brokerage models: forgiving, alias-aware, empty-str→None."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _empty_strings_to_none(cls, data: Any) -> Any:
        """TS returns ``""`` for absent numerics; turn those into None so typed
        fields validate. Non-numeric identifiers are unaffected in practice."""
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data


# ---------------------------------------------------------------------------
# C1 — Accounts
# ---------------------------------------------------------------------------


class Account(_TSModel):
    """A brokerage account (C1)."""

    account_id: str = Field(..., alias="AccountID")
    account_type: str | None = Field(None, alias="AccountType")
    currency: str | None = Field(None, alias="Currency")
    status: str | None = Field(None, alias="Status")
    alias: str | None = Field(None, alias="Alias")
    account_detail: dict[str, Any] | None = Field(None, alias="AccountDetail")


# ---------------------------------------------------------------------------
# C2 / C3 — Balances
# ---------------------------------------------------------------------------


class BalanceDetail(_TSModel):
    """Nested ``BalanceDetail`` object inside a balance."""

    cost_of_positions: float | None = Field(None, alias="CostOfPositions")
    day_trades: str | None = Field(None, alias="DayTrades")
    day_trading_marginable_buying_power: float | None = Field(
        None, alias="DayTradingMarginableBuyingPower"
    )
    maintenance_rate: float | None = Field(None, alias="MaintenanceRate")
    overnight_buying_power: float | None = Field(None, alias="OvernightBuyingPower")
    realized_profit_loss: float | None = Field(None, alias="RealizedProfitLoss")
    required_margin: float | None = Field(None, alias="RequiredMargin")
    unrealized_profit_loss: float | None = Field(None, alias="UnrealizedProfitLoss")
    unsettled_funds: float | None = Field(None, alias="UnsettledFunds")


class CurrencyDetail(_TSModel):
    """Nested per-currency detail (futures / forex accounts)."""

    currency: str | None = Field(None, alias="Currency")
    cash_balance: float | None = Field(None, alias="CashBalance")
    commission: float | None = Field(None, alias="Commission")
    realized_profit_loss: float | None = Field(None, alias="RealizedProfitLoss")
    unrealized_profit_loss: float | None = Field(None, alias="UnrealizedProfitLoss")


class Balances(_TSModel):
    """Real-time or beginning-of-day balances for an account (C2 / C3)."""

    account_id: str = Field(..., alias="AccountID")
    account_type: str | None = Field(None, alias="AccountType")
    cash_balance: float | None = Field(None, alias="CashBalance")
    buying_power: float | None = Field(None, alias="BuyingPower")
    equity: float | None = Field(None, alias="Equity")
    market_value: float | None = Field(None, alias="MarketValue")
    todays_profit_loss: float | None = Field(None, alias="TodaysProfitLoss")
    uncleared_deposit: float | None = Field(None, alias="UnclearedDeposit")
    balance_detail: BalanceDetail | None = Field(None, alias="BalanceDetail")
    currency_details: list[CurrencyDetail] | None = Field(None, alias="CurrencyDetails")


class BeginningOfDayBalances(Balances):
    """Beginning-of-day balances (C3). Same shape as :class:`Balances`."""


# ---------------------------------------------------------------------------
# C4 — Positions
# ---------------------------------------------------------------------------


class Position(_TSModel):
    """An open position (C4)."""

    account_id: str | None = Field(None, alias="AccountID")
    position_id: str | None = Field(None, alias="PositionID")
    symbol: str = Field(..., alias="Symbol")
    asset_type: str | None = Field(None, alias="AssetType")
    quantity: float | None = Field(None, alias="Quantity")
    long_short: str | None = Field(None, alias="LongShort")
    average_price: float | None = Field(None, alias="AveragePrice")
    last: float | None = Field(None, alias="Last")
    bid: float | None = Field(None, alias="Bid")
    ask: float | None = Field(None, alias="Ask")
    market_value: float | None = Field(None, alias="MarketValue")
    total_cost: float | None = Field(None, alias="TotalCost")
    unrealized_profit_loss: float | None = Field(None, alias="UnrealizedProfitLoss")
    unrealized_profit_loss_percent: float | None = Field(
        None, alias="UnrealizedProfitLossPercent"
    )
    unrealized_profit_loss_qty: float | None = Field(None, alias="UnrealizedProfitLossQty")
    todays_profit_loss: float | None = Field(None, alias="TodaysProfitLoss")
    initial_requirement: float | None = Field(None, alias="InitialRequirement")
    maintenance_margin: float | None = Field(None, alias="MaintenanceMargin")
    timestamp: str | None = Field(None, alias="Timestamp")


# ---------------------------------------------------------------------------
# C5 / C6 / C7 / C8 — Orders
# ---------------------------------------------------------------------------


class OrderLeg(_TSModel):
    """A single leg of an order."""

    symbol: str | None = Field(None, alias="Symbol")
    asset_type: str | None = Field(None, alias="AssetType")
    quantity: float | None = Field(None, alias="QuantityOrdered")
    exec_quantity: float | None = Field(None, alias="ExecQuantity")
    buy_or_sell: str | None = Field(None, alias="BuyOrSell")
    open_or_close: str | None = Field(None, alias="OpenOrClose")
    execution_price: float | None = Field(None, alias="ExecutionPrice")


class Order(_TSModel):
    """A working / today's order (C5 / C6) — also reused for history (C7 / C8)."""

    account_id: str | None = Field(None, alias="AccountID")
    order_id: str = Field(..., alias="OrderID")
    status: str | None = Field(None, alias="Status")
    status_description: str | None = Field(None, alias="StatusDescription")
    order_type: str | None = Field(None, alias="OrderType")
    symbol: str | None = Field(None, alias="Symbol")
    quantity: float | None = Field(None, alias="Quantity")
    filled_quantity: float | None = Field(None, alias="FilledQuantity")
    remaining_quantity: float | None = Field(None, alias="UnfilledQuantity")
    limit_price: float | None = Field(None, alias="LimitPrice")
    stop_price: float | None = Field(None, alias="StopPrice")
    filled_price: float | None = Field(None, alias="FilledPrice")
    duration: str | None = Field(None, alias="Duration")
    routing: str | None = Field(None, alias="Routing")
    opened_datetime: str | None = Field(None, alias="OpenedDateTime")
    closed_datetime: str | None = Field(None, alias="ClosedDateTime")
    commission_fee: float | None = Field(None, alias="CommissionFee")
    legs: list[OrderLeg] | None = Field(None, alias="Legs")


class HistoricalOrder(Order):
    """Historical order (C7 / C8). Same shape as :class:`Order`."""


# ---------------------------------------------------------------------------
# C9 — Wallets (crypto)
# ---------------------------------------------------------------------------


class Wallet(_TSModel):
    """A crypto wallet balance (C9).

    Field aliases match the live v3 response (BalanceAvailableForTrading,
    BalanceAvailableForWithdrawal, UnrealizedProfitLossAccountCurrency, …).
    """

    account_id: str | None = Field(None, alias="AccountID")
    currency: str | None = Field(None, alias="Currency")
    balance: float | None = Field(None, alias="Balance")
    available_for_trading: float | None = Field(
        None, alias="BalanceAvailableForTrading"
    )
    available_for_withdrawal: float | None = Field(
        None, alias="BalanceAvailableForWithdrawal"
    )
    unrealized_profit_loss: float | None = Field(
        None, alias="UnrealizedProfitLossAccountCurrency"
    )
    status: str | None = Field(None, alias="Status")


# ---------------------------------------------------------------------------
# Envelope parsers
# ---------------------------------------------------------------------------


def _parse_list(raw: Any, key: str, model: type[BaseModel]) -> list[Any]:
    """Parse a TS list envelope ``{key: [...], "Errors": [...]}`` into models.

    Tolerates both the envelope shape and a bare list. Items that fail
    validation are skipped rather than raising, so one malformed row never
    sinks the whole response.
    """
    if isinstance(raw, dict):
        items = raw.get(key, [])
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    if not isinstance(items, list):
        return []
    out: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            out.append(model.model_validate(item))
    return out


def parse_accounts_response(raw: Any) -> list[Account]:
    """Parse C1 ``{"Accounts": [...]}``."""
    return _parse_list(raw, "Accounts", Account)


def parse_balances_response(raw: Any) -> list[Balances]:
    """Parse C2 ``{"Balances": [...], "Errors": [...]}``."""
    return _parse_list(raw, "Balances", Balances)


def parse_bod_balances_response(raw: Any) -> list[BeginningOfDayBalances]:
    """Parse C3 ``{"BODBalances": [...], "Errors": [...]}`` (falls back to "Balances")."""
    if isinstance(raw, dict) and "BODBalances" in raw:
        return _parse_list(raw, "BODBalances", BeginningOfDayBalances)
    return _parse_list(raw, "Balances", BeginningOfDayBalances)


def parse_positions_response(raw: Any) -> list[Position]:
    """Parse C4 ``{"Positions": [...], "Errors": [...]}``."""
    return _parse_list(raw, "Positions", Position)


def parse_orders_response(raw: Any) -> list[Order]:
    """Parse C5 / C6 ``{"Orders": [...], "Errors": [...]}``."""
    return _parse_list(raw, "Orders", Order)


def parse_historical_orders_response(raw: Any) -> list[HistoricalOrder]:
    """Parse C7 / C8 ``{"Orders": [...], "Errors": [...]}``."""
    return _parse_list(raw, "Orders", HistoricalOrder)


def parse_wallets_response(raw: Any) -> list[Wallet]:
    """Parse C9 ``{"Wallets": [...], "Errors": [...]}``."""
    return _parse_list(raw, "Wallets", Wallet)
