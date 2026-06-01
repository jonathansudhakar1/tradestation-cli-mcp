"""Tests for the generated models.py — import + pydantic roundtrip validation.

Tests:
- Sample generated models import cleanly
- Models can be constructed from synthetic JSON payloads
- Pydantic model_dump / model_validate roundtrips work
- Enums are usable
"""

from __future__ import annotations

import importlib
import sys
from enum import Enum
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_models() -> Any:
    """Import the generated models module, forcing a fresh load."""
    mod_name = "tradestation._generated.models"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Basic import tests
# ---------------------------------------------------------------------------


def test_models_module_importable() -> None:
    """The generated models module must be importable."""
    models = _get_models()
    assert models is not None


def test_models_module_has_many_names() -> None:
    """dir(models) must contain more than 30 names (AC4)."""
    models = _get_models()
    names = dir(models)
    assert len(names) > 30, f"Expected > 30 names, got {len(names)}: {names}"


def test_models_has_pydantic_base_model() -> None:
    """At least one class in models must be a pydantic BaseModel subclass."""
    import pydantic

    models = _get_models()
    found = [
        name
        for name in dir(models)
        if isinstance(getattr(models, name, None), type)
        and issubclass(getattr(models, name), pydantic.BaseModel)
    ]
    assert len(found) >= 5, f"Expected >= 5 BaseModel subclasses, found {len(found)}: {found}"


def test_models_has_enums() -> None:
    """At least one class in models must be an Enum subclass."""
    models = _get_models()
    found = [
        name
        for name in dir(models)
        if isinstance(getattr(models, name, None), type)
        and issubclass(getattr(models, name), Enum)
    ]
    assert len(found) >= 3, f"Expected >= 3 Enum subclasses, found {len(found)}: {found}"


# ---------------------------------------------------------------------------
# Error model roundtrip
# ---------------------------------------------------------------------------


def test_error_model_roundtrip() -> None:
    """Error model can be constructed from and dumped to dict."""
    models = _get_models()
    Error = models.Error

    payload = {
        "TraceId": "12345678-1234-5678-1234-567812345678",
        "StatusCode": 404,
        "Message": "Not found",
    }
    obj = Error.model_validate(payload)
    assert obj.status_code == 404
    assert obj.message == "Not found"

    dumped = obj.model_dump(by_alias=True, exclude_none=True)
    assert dumped["StatusCode"] == 404
    assert dumped["Message"] == "Not found"


def test_error_model_all_none() -> None:
    """Error model with no fields set must be constructable."""
    models = _get_models()
    Error = models.Error

    obj = Error.model_validate({})
    assert obj.status_code is None
    assert obj.message is None
    assert obj.trace_id is None


# ---------------------------------------------------------------------------
# Symbol definition roundtrip
# ---------------------------------------------------------------------------


def test_symbol_definition_roundtrip() -> None:
    """SymbolDefinition can be validated from a synthetic payload."""
    models = _get_models()
    SymbolDefinition = models.SymbolDefinition

    # SymbolDefinition uses: Category, Country, Currency, Description, Exchange, Name, etc.
    # Country is an Enum with values "US", "DE", "CA" — use the code not full name
    payload = {
        "Name": "AAPL",
        "Category": "Stock",
        "Description": "Apple Inc.",
        "Exchange": "NASDAQ",
        "Country": "US",
        "Currency": "USD",
    }
    obj = SymbolDefinition.model_validate(payload)
    assert obj.category == "Stock"
    assert obj.description == "Apple Inc."


def test_symbol_definition_partial() -> None:
    """SymbolDefinition must accept partial data (all fields optional)."""
    models = _get_models()
    SymbolDefinition = models.SymbolDefinition

    # All fields in SymbolDefinition are optional
    obj = SymbolDefinition.model_validate({"Name": "ES.M26", "Category": "Future"})
    assert obj.category == "Future"


# ---------------------------------------------------------------------------
# Quote definition roundtrip
# ---------------------------------------------------------------------------


def test_quote_definition_item_roundtrip() -> None:
    """QuoteDefinitionItem must accept a synthetic quote payload."""
    models = _get_models()
    QuoteDefinitionItem = models.QuoteDefinitionItem

    payload = {
        "Symbol": "AAPL",
        "Ask": 195.50,
        "Bid": 195.48,
        "Last": 195.49,
        "Volume": 1234567,
    }
    obj = QuoteDefinitionItem.model_validate(payload)
    assert obj.ask == pytest.approx(195.50)
    assert obj.bid == pytest.approx(195.48)


def test_quote_definition_list_roundtrip() -> None:
    """QuoteDefinition (RootModel of list) must accept a list payload."""
    models = _get_models()
    QuoteDefinition = models.QuoteDefinition

    payload = [
        {"Symbol": "AAPL", "Ask": 195.50, "Bid": 195.48},
        {"Symbol": "MSFT", "Ask": 420.10, "Bid": 420.05},
    ]
    obj = QuoteDefinition.model_validate(payload)
    assert len(obj.root) == 2
    assert obj.root[0].symbol == "AAPL"
    assert obj.root[1].symbol == "MSFT"


# ---------------------------------------------------------------------------
# Account balances roundtrip
# ---------------------------------------------------------------------------


def test_account_balances_item_roundtrip() -> None:
    """AccountBalancesDefinitionItem must accept a synthetic balance payload."""
    models = _get_models()
    AccountBalancesDefinitionItem = models.AccountBalancesDefinitionItem

    # Uses: Key, Name, DisplayName, MarketValue, etc. (no AccountID field)
    payload = {
        "Key": "11111111",
        "Name": "Individual",
        "DisplayName": "My Account",
        "MarketValue": 50000.00,
        "RealTimeEquity": 100000.00,
    }
    obj = AccountBalancesDefinitionItem.model_validate(payload)
    # Key is a number field in v2 swagger (account number stored as float)
    assert obj.key == pytest.approx(11111111.0)
    assert obj.market_value == pytest.approx(50000.0)


# ---------------------------------------------------------------------------
# Order request roundtrip
# ---------------------------------------------------------------------------


def test_order_request_definition_roundtrip() -> None:
    """OrderRequestDefinition must accept a synthetic order request payload."""
    models = _get_models()
    OrderRequestDefinition = models.OrderRequestDefinition

    # Required fields: AccountKey, AssetType, Duration, OrderType, Quantity, Symbol, TradeAction
    payload = {
        "AccountKey": "11111111",
        "Symbol": "AAPL",
        "Quantity": "10",
        "OrderType": "Market",
        "TradeAction": "BUY",
        "AssetType": "EQ",
        "Duration": "DAY",
        "Route": "Intelligent",
    }
    obj = OrderRequestDefinition.model_validate(payload)
    assert obj.symbol == "AAPL"
    assert obj.quantity == "10"


def test_order_request_dump_roundtrip() -> None:
    """OrderRequestDefinition dump → validate must be lossless for set fields."""
    models = _get_models()
    OrderRequestDefinition = models.OrderRequestDefinition

    payload = {
        "AccountKey": "22222222",
        "Symbol": "MSFT",
        "Quantity": "5",
        "OrderType": "Limit",
        "TradeAction": "SELL",
        "AssetType": "EQ",
        "Duration": "DAY",
    }
    obj1 = OrderRequestDefinition.model_validate(payload)
    dumped = obj1.model_dump(by_alias=True, exclude_none=True)
    obj2 = OrderRequestDefinition.model_validate(dumped)
    assert obj1.symbol == obj2.symbol
    assert obj1.quantity == obj2.quantity


# ---------------------------------------------------------------------------
# Activation trigger roundtrip
# ---------------------------------------------------------------------------


def test_activation_trigger_definition_roundtrip() -> None:
    """ActivationTriggerDefinition must accept a synthetic trigger payload."""
    models = _get_models()
    ActivationTriggerDefinition = models.ActivationTriggerDefinition

    payload = {
        "Key": "STT",
        "Name": "Stop On Trade",
        "SecurityTypes": ["Stock", "Option"],
    }
    obj = ActivationTriggerDefinition.model_validate(payload)
    assert obj is not None


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


def test_asset_type_enum() -> None:
    """AssetType enum must be usable."""
    models = _get_models()
    AssetType = models.AssetType
    assert isinstance(AssetType, type)
    assert issubclass(AssetType, Enum)
    # Check it has members
    members = list(AssetType)
    assert len(members) >= 1


def test_order_type_enum() -> None:
    """OrderType enum must contain standard order types."""
    models = _get_models()
    OrderType = models.OrderType
    values = {m.value for m in OrderType}
    # Standard types that should be in there
    assert any(v.lower() in ("market", "limit", "stop", "stoplimit") for v in values), (
        f"Expected standard order type values in {values}"
    )


def test_side_enum() -> None:
    """Side enum must have members (B = Buy, S = Sell in v2 swagger)."""
    models = _get_models()
    Side = models.Side
    values = {m.value for m in Side}
    # v2 swagger uses single-char codes: B, S, T (sell short), C (buy to cover)
    assert "B" in values, f"'B' (Buy) not found in Side values: {values}"
    assert "S" in values, f"'S' (Sell) not found in Side values: {values}"
