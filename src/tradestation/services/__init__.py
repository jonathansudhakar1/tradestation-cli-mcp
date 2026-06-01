"""tradestation.services — one module per TradeStation API category.

Services are accessed via the client, not imported directly::

    ts = TradeStationClient.from_default_credentials()
    ts.market_data  # MarketDataService
    ts.brokerage  # BrokerageService
    ts.order_execution  # OrderExecutionService
"""

from tradestation.services.base import BaseService
from tradestation.services.brokerage import BrokerageService
from tradestation.services.market_data import MarketDataService
from tradestation.services.order_execution import OrderExecutionService

__all__ = [
    "BaseService",
    "BrokerageService",
    "MarketDataService",
    "OrderExecutionService",
]
