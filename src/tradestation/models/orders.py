"""Order request / response Pydantic models (D-series endpoints).

Request models build the TradeStation v3 order-execution JSON. Response
models are forgiving (``extra="allow"``) like the rest of the library.

v3 order request shape (POST /v3/orderexecution/orders)::

    {
      "AccountID": "11111111",
      "Symbol": "AAPL",
      "Quantity": "100",
      "OrderType": "Market",
      "TradeAction": "BUY",
      "TimeInForce": {"Duration": "DAY"},
      "Route": "Intelligent",
      "LimitPrice": "178.00"      # limit / stop-limit only
      "StopPrice": "170.00"       # stop / stop-limit only
    }

See docs/05-python-library.md §"Models (sketch)".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tradestation.enums import OrderType, Side, TimeInForce


def _trade_action(side: Side) -> str:
    """Map a :class:`Side` enum to the TS ``TradeAction`` string.

    TS uses concatenated tokens (``BUYTOCOVER``, ``SELLSHORT``, ``BUYTOOPEN`` …),
    so we simply strip the underscores from the enum value.
    """
    return side.value.replace("_", "")


def _fmt_qty(quantity: float) -> str:
    """Format an order quantity for the API.

    Whole numbers must be sent without a trailing ``.0`` (the API rejects
    ``"1.0"`` for equity orders), while fractional quantities (crypto) keep
    their decimals.
    """
    if quantity == int(quantity):
        return str(int(quantity))
    return repr(quantity)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class OrderRequest(BaseModel):
    """Base single-leg order request.

    Use a concrete subclass (:class:`MarketOrderRequest`, etc.) — they fix the
    ``order_type`` so the right price fields are required.
    """

    model_config = ConfigDict(use_enum_values=False)

    account_id: str
    symbol: str
    quantity: float
    side: Side
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    gtd_expiration: str | None = None
    route: str = "Intelligent"
    limit_price: float | None = None
    stop_price: float | None = None
    all_or_none: bool = False
    activation_trigger: str | None = None

    def to_api(self) -> dict[str, Any]:
        """Build the v3 JSON body for this order."""
        tif: dict[str, Any] = {"Duration": self.time_in_force.value}
        if self.time_in_force is TimeInForce.GTD and self.gtd_expiration:
            tif["Expiration"] = self.gtd_expiration

        body: dict[str, Any] = {
            "AccountID": self.account_id,
            "Symbol": self.symbol,
            "Quantity": _fmt_qty(self.quantity),
            "OrderType": self.order_type.value,
            "TradeAction": _trade_action(self.side),
            "TimeInForce": tif,
            "Route": self.route,
        }
        if self.limit_price is not None:
            body["LimitPrice"] = str(self.limit_price)
        if self.stop_price is not None:
            body["StopPrice"] = str(self.stop_price)
        if self.all_or_none:
            body.setdefault("AdvancedOptions", {})["AllOrNone"] = True
        if self.activation_trigger is not None:
            body.setdefault("AdvancedOptions", {})["TrailingStop"] = {}
            body["AdvancedOptions"]["MarketActivationRules"] = [
                {"TriggerKey": self.activation_trigger}
            ]
        return body


class MarketOrderRequest(OrderRequest):
    """A market order (no price fields)."""

    order_type: OrderType = Field(default=OrderType.MARKET, frozen=True)


class LimitOrderRequest(OrderRequest):
    """A limit order (requires ``limit_price``)."""

    order_type: OrderType = Field(default=OrderType.LIMIT, frozen=True)
    limit_price: float


class StopOrderRequest(OrderRequest):
    """A stop-market order (requires ``stop_price``)."""

    order_type: OrderType = Field(default=OrderType.STOP_MARKET, frozen=True)
    stop_price: float


class StopLimitOrderRequest(OrderRequest):
    """A stop-limit order (requires both ``stop_price`` and ``limit_price``)."""

    order_type: OrderType = Field(default=OrderType.STOP_LIMIT, frozen=True)
    stop_price: float
    limit_price: float


class OrderGroupRequest(BaseModel):
    """A grouped order: OCO (one-cancels-other), BRK (bracket), or NORMAL (OSO).

    ``order_type`` is the TS group type string: ``"OCO"``, ``"BRK"``, or
    ``"NORMAL"``. ``orders`` is the list of child single-leg requests.
    """

    model_config = ConfigDict(use_enum_values=False)

    group_type: str = "OCO"
    orders: list[OrderRequest]

    def to_api(self) -> dict[str, Any]:
        """Build the v3 JSON body for the order group."""
        return {
            "Type": self.group_type,
            "Orders": [o.to_api() for o in self.orders],
        }


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OrderConfirmation(BaseModel):
    """Preview of an order (D1 / D5) — fees + buying-power impact."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    order_confirm_id: str | None = Field(None, alias="OrderConfirmID")
    account_id: str | None = Field(None, alias="AccountID")
    symbol: str | None = Field(None, alias="Symbol")
    quantity: str | None = Field(None, alias="Quantity")
    order_type: str | None = Field(None, alias="OrderType")
    estimated_price: str | None = Field(None, alias="EstimatedPrice")
    estimated_cost: str | None = Field(None, alias="EstimatedCost")
    estimated_commission: str | None = Field(None, alias="EstimatedCommission")
    commission: str | None = Field(None, alias="Commission")
    summary_message: str | None = Field(None, alias="SummaryMessage")
    route: str | None = Field(None, alias="Route")


class OrderResponseItem(BaseModel):
    """A single result entry inside an order-placement response."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    order_id: str | None = Field(None, alias="OrderID")
    message: str | None = Field(None, alias="Message")
    error: str | None = Field(None, alias="Error")


class OrderResponse(BaseModel):
    """Response from placing / replacing / cancelling an order (D2 / D3 / D4 / D6)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    orders: list[OrderResponseItem] = Field(default_factory=list, alias="Orders")
    errors: list[dict[str, Any]] | None = Field(None, alias="Errors")

    @property
    def rejected(self) -> bool:
        """True if any result item carries an ``Error``."""
        return any(o.error for o in self.orders)


class ActivationTrigger(BaseModel):
    """An activation trigger (D7)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    key: str | None = Field(None, alias="Key")
    name: str | None = Field(None, alias="Name")
    description: str | None = Field(None, alias="Description")


class ExecutionRoute(BaseModel):
    """An execution route (D8)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = Field(None, alias="Id")
    name: str | None = Field(None, alias="Name")
    asset_types: list[str] | None = Field(None, alias="AssetTypes")


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def parse_order_response(raw: Any) -> OrderResponse:
    """Parse a D2/D3/D4/D6 placement/cancel response."""
    if isinstance(raw, dict):
        return OrderResponse.model_validate(raw)
    return OrderResponse.model_validate({})


def parse_confirmations(raw: Any) -> list[OrderConfirmation]:
    """Parse a D1/D5 confirm response ``{"Confirmations": [...]}`` (or bare list)."""
    if isinstance(raw, dict):
        items = raw.get("Confirmations", raw.get("Orders", []))
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    if not isinstance(items, list):
        return []
    return [OrderConfirmation.model_validate(c) for c in items if isinstance(c, dict)]


def parse_activation_triggers(raw: Any) -> list[ActivationTrigger]:
    """Parse D7 ``{"ActivationTriggers": [...]}``."""
    items = raw.get("ActivationTriggers", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [ActivationTrigger.model_validate(t) for t in items if isinstance(t, dict)]


def parse_routes(raw: Any) -> list[ExecutionRoute]:
    """Parse D8 ``{"Routes": [...]}``."""
    items = raw.get("Routes", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [ExecutionRoute.model_validate(r) for r in items if isinstance(r, dict)]
