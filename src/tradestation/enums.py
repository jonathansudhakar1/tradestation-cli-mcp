"""StrEnum types shared across the tradestation library.

See docs/05-python-library.md and docs/03-endpoint-inventory.md for usage.

Enums defined here:
    Side, OrderType, TimeInForce, BarUnit, Environment,
    OrderStatus, AssetType, MarketSession, StreamMessageType
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    import enum

    class StrEnum(str, enum.Enum):
        """Backport of ``enum.StrEnum`` for Python 3.10.

        Mirrors native ``enum.StrEnum`` (3.11+): ``str(member)`` and
        ``format(member)`` return the string *value* (e.g. ``"sim"``), not the
        ``"Class.MEMBER"`` repr that a plain ``(str, Enum)`` would produce.
        """

        def __str__(self) -> str:
            return str.__str__(self)

        def __format__(self, format_spec: str) -> str:
            return str.__format__(self, format_spec)


class Side(StrEnum):
    """Order side — buy or sell."""

    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"
    BUY_TO_OPEN = "BUY_TO_OPEN"
    BUY_TO_CLOSE = "BUY_TO_CLOSE"
    SELL_TO_OPEN = "SELL_TO_OPEN"
    SELL_TO_CLOSE = "SELL_TO_CLOSE"


class OrderType(StrEnum):
    """Order type / execution instruction."""

    MARKET = "Market"
    LIMIT = "Limit"
    STOP_MARKET = "StopMarket"
    STOP_LIMIT = "StopLimit"


class TimeInForce(StrEnum):
    """Time-in-force / duration of an order."""

    DAY = "DAY"
    GTC = "GTC"
    GTD = "GTD"
    IOC = "IOC"
    FOK = "FOK"
    OPG = "OPG"
    CLO = "CLO"


class BarUnit(StrEnum):
    """Unit for bar chart intervals (used with B1/B12 endpoints)."""

    MINUTE = "Minute"
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    TICK = "Tick"
    VOLUME = "Volume"


class Environment(StrEnum):
    """TradeStation API environment.

    Determines the base URL used for all requests:
    - LIVE: ``https://api.tradestation.com/v3``
    - SIM:  ``https://sim-api.tradestation.com/v3``
    """

    LIVE = "live"
    SIM = "sim"


class OrderStatus(StrEnum):
    """Order lifecycle status values returned by the brokerage endpoints."""

    ACK = "ACK"
    RECEIVED = "Received"
    SENT = "Sent"
    QUEUED = "Queued"
    CONDITIONMET = "ConditionMet"
    OPENED = "Opened"
    WORKING = "FPO"
    FILLED = "Filled"
    PARTIALLY_FILLED = "PartiallyFilled"
    CANCELLED = "Cancelled"
    REPLACED = "Replaced"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    SUSPENDED = "Suspended"
    FAILED = "Failed"
    TOO_LATE = "TooLateToCancel"
    CONDITIONAL = "Conditional"


class AssetType(StrEnum):
    """Asset type / product family for a symbol."""

    STOCK = "STOCK"
    STOCKOPTION = "STOCKOPTION"
    FUTURE = "FUTURE"
    FUTUREOPTION = "FUTUREOPTION"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    INDEX = "INDEX"
    MUTUAL_FUND = "MUTUALFUND"
    FUND = "FUND"
    BOND = "BOND"


class MarketSession(StrEnum):
    """Session template for bar charts and streaming data."""

    DEFAULT = "Default"
    EXTENDED_HOURS = "USEQPreAndPost"
    US_EQ_PRE = "USEQPre"
    US_EQ_POST = "USEQPost"
    ALL = "All"


class StreamMessageType(StrEnum):
    """Discriminator tag present in streaming JSON frames.

    TradeStation streaming endpoints return newline-delimited JSON where each
    line carries a ``Type`` field. This enum names the known values.
    """

    HEARTBEAT = "Heartbeat"
    QUOTE = "Quote"
    BAR = "Bar"
    MARKET_DEPTH_QUOTE = "MarketDepthQuote"
    MARKET_DEPTH_AGGREGATE = "MarketDepthAggregate"
    ORDER = "Order"
    POSITION = "Position"
    WALLET = "Wallet"
    OPTION_CHAIN = "OptionChain"
    OPTION_QUOTE = "OptionQuote"
    ERROR = "Error"
    STATUS = "Status"
