"""Market data Pydantic models.

Covers B2 GET /v3/marketdata/quotes/{symbols} response shape.

v3 reality (confirmed against live SIM):
- Response is ``{"Quotes": [...], "Errors": [...]}`` — NOT a bare list.
- All numeric fields are **strings** (e.g. ``"306.03"`` not ``306.03``).
- ``MarketFlags`` is a nested object.
- Extra fields not in the v2 swagger (VWAP, LastSize, LastVenue, PreviousClose, etc.)
  are allowed via ``extra="allow"``.

See docs/05-python-library.md §"Models".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MarketFlags(BaseModel):
    """Nested market-flags object returned inside each Quote."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    is_halted: bool | None = Field(None, alias="IsHalted")
    is_delayed: bool | None = Field(None, alias="IsDelayed")
    is_hard_to_borrow: bool | None = Field(None, alias="IsHardToBorrow")
    is_bats: bool | None = Field(None, alias="IsBats")


def _to_float_or_none(v: Any) -> float | None:
    """Safely coerce a string/int/float/None to float."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(v: Any) -> int | None:
    """Safely coerce a string/int/float/None to int."""
    f = _to_float_or_none(v)
    if f is None:
        return None
    return int(f)


class Quote(BaseModel):
    """Snapshot quote for a single instrument (B2).

    Field names use snake_case; aliases match the PascalCase names returned
    by the TradeStation v3 API.  All fields except ``symbol`` and ``last``
    are optional so that partial or unusual responses (crypto, futures) never
    crash the parser.

    Numeric values from the API are strings; the validator coerces them.
    Unknown fields are stored in the model's ``__pydantic_extra__`` dict.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )

    # --- Core identity ---
    symbol: str = Field(..., alias="Symbol")

    # --- Prices (all come as strings from the API) ---
    last: float | None = Field(None, alias="Last")
    bid: float | None = Field(None, alias="Bid")
    ask: float | None = Field(None, alias="Ask")
    open: float | None = Field(None, alias="Open")
    high: float | None = Field(None, alias="High")
    low: float | None = Field(None, alias="Low")
    close: float | None = Field(None, alias="Close")
    previous_close: float | None = Field(None, alias="PreviousClose")

    # --- Size ---
    bid_size: int | None = Field(None, alias="BidSize")
    ask_size: int | None = Field(None, alias="AskSize")
    last_size: int | None = Field(None, alias="LastSize")

    # --- Change ---
    net_change: float | None = Field(None, alias="NetChange")
    net_change_pct: float | None = Field(None, alias="NetChangePct")

    # --- Volume ---
    volume: int | None = Field(None, alias="Volume")
    previous_volume: int | None = Field(None, alias="PreviousVolume")
    daily_open_interest: int | None = Field(None, alias="DailyOpenInterest")

    # --- 52-week range ---
    high_52_week: float | None = Field(None, alias="High52Week")
    low_52_week: float | None = Field(None, alias="Low52Week")
    high_52_week_timestamp: str | None = Field(None, alias="High52WeekTimestamp")
    low_52_week_timestamp: str | None = Field(None, alias="Low52WeekTimestamp")

    # --- Trade metadata ---
    trade_time: str | None = Field(None, alias="TradeTime")
    last_venue: str | None = Field(None, alias="LastVenue")
    vwap: float | None = Field(None, alias="VWAP")
    tick_size_tier: str | None = Field(None, alias="TickSizeTier")

    # --- Flags ---
    market_flags: MarketFlags | None = Field(None, alias="MarketFlags")
    restrictions: list[str] | None = Field(None, alias="Restrictions")

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Quote:
        """Validate and coerce a quote dict from the v3 API.

        Applies string-to-numeric coercion before passing to Pydantic so the
        validator sees proper types.
        """
        if isinstance(obj, dict):
            obj = _coerce_quote_strings(obj)
        return super().model_validate(obj, **kwargs)

    @property
    def last_utc(self) -> datetime | None:
        """Parse ``TradeTime`` as a UTC datetime, or return None."""
        if not self.trade_time:
            return None
        try:
            return datetime.fromisoformat(self.trade_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    @property
    def is_halted(self) -> bool:
        """Return True if the MarketFlags indicate the symbol is halted."""
        if self.market_flags is None:
            return False
        return bool(self.market_flags.is_halted)


# ---------------------------------------------------------------------------
# String-to-numeric coercion helper
# ---------------------------------------------------------------------------

_FLOAT_FIELDS = {
    "Last", "Bid", "Ask", "Open", "High", "Low", "Close", "PreviousClose",
    "NetChange", "NetChangePct", "High52Week", "Low52Week", "VWAP",
}
_INT_FIELDS = {
    "BidSize", "AskSize", "LastSize", "Volume", "PreviousVolume", "DailyOpenInterest",
}


def _coerce_quote_strings(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with numeric-string fields coerced to numbers.

    The TS v3 API returns all numeric values as JSON strings.  Pydantic's
    json-mode coercion handles this, but model_validate(dict) does not by
    default for strict types.  We apply a simple pre-pass.
    """
    out = dict(data)
    for field_name in _FLOAT_FIELDS:
        if field_name in out and isinstance(out[field_name], str):
            try:
                out[field_name] = float(out[field_name])
            except (ValueError, TypeError):
                out[field_name] = None
    for field_name in _INT_FIELDS:
        if field_name in out and isinstance(out[field_name], str):
            try:
                out[field_name] = int(float(out[field_name]))
            except (ValueError, TypeError):
                out[field_name] = None
    return out


# ---------------------------------------------------------------------------
# Response envelope parser
# ---------------------------------------------------------------------------


class Bar(BaseModel):
    """A single OHLC bar (B1 barcharts).

    v3 reality: the barcharts response is ``{"Bars": [...]}``; numeric fields
    arrive as strings; ``TimeStamp`` is ISO-8601 UTC. Unknown fields allowed.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    open: float | None = Field(None, alias="Open")
    high: float | None = Field(None, alias="High")
    low: float | None = Field(None, alias="Low")
    close: float | None = Field(None, alias="Close")
    timestamp: str | None = Field(None, alias="TimeStamp")
    total_volume: int | None = Field(None, alias="TotalVolume")
    total_trades: int | None = Field(None, alias="TotalTrades")
    open_interest: int | None = Field(None, alias="OpenInterest")
    up_volume: int | None = Field(None, alias="UpVolume")
    down_volume: int | None = Field(None, alias="DownVolume")
    high_low_price: float | None = Field(None, alias="HighLowPriceMidpoint")
    is_realtime: bool | None = Field(None, alias="IsRealtime")
    is_end_of_history: bool | None = Field(None, alias="IsEndOfHistory")
    bar_status: str | None = Field(None, alias="BarStatus")

    @property
    def datetime_utc(self) -> datetime | None:
        """Parse ``TimeStamp`` as a UTC datetime, or return None."""
        if not self.timestamp:
            return None
        try:
            return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None


def parse_bars_response(raw: Any) -> list[Bar]:
    """Parse the raw v3 barcharts response ``{"Bars": [...]}`` into models.

    Numeric strings are coerced by Pydantic's lax mode. Unknown fields are
    preserved. A bare list is also tolerated.
    """
    if isinstance(raw, dict):
        bars = raw.get("Bars", [])
    elif isinstance(raw, list):
        bars = raw
    else:
        bars = []
    if not isinstance(bars, list):
        return []
    return [Bar.model_validate(b) for b in bars if isinstance(b, dict)]


def parse_quotes_response(raw: dict[str, Any]) -> list[Quote]:
    """Parse the raw v3 quote response into a list of :class:`Quote` models.

    The v3 API returns:
    ``{"Quotes": [...], "Errors": [...]}``

    Any symbols with errors are silently skipped (they appear in ``Errors``
    not in ``Quotes``).  Unknown fields inside each quote are stored in
    ``model.__pydantic_extra__`` and do not raise.

    Args:
        raw: The decoded JSON dict from the API response.

    Returns:
        A list of :class:`Quote` instances, one per valid symbol.
    """
    quotes_list = raw.get("Quotes", [])
    if not isinstance(quotes_list, list):
        return []

    result: list[Quote] = []
    unexpected_fields: set[str] = set()

    for item in quotes_list:
        if not isinstance(item, dict):
            continue
        # Collect any top-level fields we didn't expect (for diagnostics)
        known = {
            "Symbol", "Last", "Bid", "Ask", "Open", "High", "Low", "Close",
            "PreviousClose", "BidSize", "AskSize", "LastSize", "NetChange",
            "NetChangePct", "Volume", "PreviousVolume", "DailyOpenInterest",
            "High52Week", "Low52Week", "High52WeekTimestamp", "Low52WeekTimestamp",
            "TradeTime", "LastVenue", "VWAP", "TickSizeTier", "MarketFlags",
            "Restrictions",
        }
        for k in item:
            if k not in known:
                unexpected_fields.add(k)

        q = Quote.model_validate(item)
        result.append(q)

    return result
