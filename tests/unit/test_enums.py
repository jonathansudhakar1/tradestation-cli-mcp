"""Guard StrEnum string behavior across Python versions.

The 3.10 ``StrEnum`` backport must match native 3.11+ ``enum.StrEnum``:
``str(member)`` and ``f"{member}"`` yield the *value* (``"sim"``), not the
``"Environment.SIM"`` repr. A plain ``(str, Enum)`` would produce the latter,
which silently corrupted the serialized credentials ``environment`` field on
Python 3.10.
"""

from __future__ import annotations

from tradestation.enums import Environment, OrderType, Side


def test_str_returns_value_not_repr() -> None:
    assert str(Environment.SIM) == "sim"
    assert str(Side.BUY) == "BUY"
    assert str(OrderType.STOP_MARKET) == "StopMarket"


def test_format_returns_value() -> None:
    assert f"{Environment.SIM}" == "sim"
    assert f"{OrderType.LIMIT}" == "Limit"


def test_value_matches_str() -> None:
    for member in Environment:
        assert str(member) == member.value
