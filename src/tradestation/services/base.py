"""BaseService — shared transport handle for all service classes.

Every concrete service (MarketDataService, BrokerageService,
OrderExecutionService) inherits from this class and uses ``self._transport``
to make HTTP calls.
"""

from __future__ import annotations

from tradestation.transport import Transport


class BaseService:
    """Concrete base for all TradeStation API service classes.

    Args:
        transport: The HTTP transport to use for all requests.  Injected by
            :class:`~tradestation.client.TradeStationClient` (or the async
            variant) so that tests can substitute a fake transport.
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
