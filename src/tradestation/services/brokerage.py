"""BrokerageService — all C-series endpoint methods.

See docs/03-endpoint-inventory.md §"C. Brokerage" for the full inventory.
See docs/05-python-library.md §"Service surface" for method signatures.

REST methods (C1-C9) are implemented. Streaming methods (C10-C13) remain
stubs pending Phase 5.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

from tradestation.models.brokerage import (
    Account,
    Balances,
    BeginningOfDayBalances,
    HistoricalOrder,
    Order,
    Position,
    Wallet,
    parse_accounts_response,
    parse_balances_response,
    parse_bod_balances_response,
    parse_historical_orders_response,
    parse_orders_response,
    parse_positions_response,
    parse_wallets_response,
)
from tradestation.services.base import BaseService
from tradestation.streaming import StreamEvent, stream_events


def _join(ids: list[str] | str) -> str:
    """Join a list of IDs (or pass through a comma string) for a path segment."""
    if isinstance(ids, str):
        return ",".join(s.strip() for s in ids.split(",") if s.strip())
    return ",".join(ids)


class BrokerageService(BaseService):
    """Service wrapping all TradeStation Brokerage v3 endpoints (C1-C13).

    Obtain via ``client.brokerage`` — do not construct directly.
    """

    # ------------------------------------------------------------------
    # C.1 — REST endpoints
    # ------------------------------------------------------------------

    async def list_accounts(self) -> list[Account]:
        """List all brokerage accounts for the authenticated user.

        Maps to: C1 GET /brokerage/accounts

        Returns:
            A list of :class:`~tradestation.models.brokerage.Account` models.

        Raises:
            tradestation.errors.ApiError: On 4xx / 5xx from the API.
            tradestation.errors.NetworkError: On transport failure.
        """
        raw = await self._transport.request("GET", "/brokerage/accounts")
        return parse_accounts_response(raw)

    async def get_balances(self, account_ids: list[str] | str) -> list[Balances]:
        """Fetch real-time balances for one or more accounts.

        Maps to: C2 GET /brokerage/accounts/{accountIDs}/balances

        Args:
            account_ids: Account IDs (list or comma-separated string).

        Returns:
            A list of :class:`~tradestation.models.brokerage.Balances` models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/balances"
        raw = await self._transport.request("GET", path)
        return parse_balances_response(raw)

    async def get_bod_balances(self, account_ids: list[str] | str) -> list[BeginningOfDayBalances]:
        """Fetch beginning-of-day balances for one or more accounts.

        Maps to: C3 GET /brokerage/accounts/{accountIDs}/balances/bod

        Args:
            account_ids: Account IDs (list or comma-separated string).

        Returns:
            A list of beginning-of-day balance models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/bodbalances"
        raw = await self._transport.request("GET", path)
        return parse_bod_balances_response(raw)

    async def get_positions(self, account_ids: list[str] | str) -> list[Position]:
        """Fetch open positions for one or more accounts.

        Maps to: C4 GET /brokerage/accounts/{accountIDs}/positions

        Args:
            account_ids: Account IDs (list or comma-separated string).

        Returns:
            A list of :class:`~tradestation.models.brokerage.Position` models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/positions"
        raw = await self._transport.request("GET", path)
        return parse_positions_response(raw)

    async def get_orders(self, account_ids: list[str] | str) -> list[Order]:
        """Fetch today's orders for one or more accounts.

        Maps to: C5 GET /brokerage/accounts/{accountIDs}/orders

        Args:
            account_ids: Account IDs (list or comma-separated string).

        Returns:
            A list of :class:`~tradestation.models.brokerage.Order` models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/orders"
        raw = await self._transport.request("GET", path)
        return parse_orders_response(raw)

    async def get_orders_by_id(
        self,
        account_ids: list[str] | str,
        order_ids: list[str] | str,
    ) -> list[Order]:
        """Fetch specific orders by order ID.

        Maps to: C6 GET /brokerage/accounts/{accountIDs}/orders/{orderIDs}

        Args:
            account_ids: Account IDs (list or comma-separated string).
            order_ids: Order IDs (list or comma-separated string).

        Returns:
            A list of :class:`~tradestation.models.brokerage.Order` models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/orders/{_join(order_ids)}"
        raw = await self._transport.request("GET", path)
        return parse_orders_response(raw)

    async def get_historical_orders(
        self,
        account_ids: list[str] | str,
        since: date,
    ) -> list[HistoricalOrder]:
        """Fetch historical orders since a given date.

        Maps to: C7 GET /brokerage/accounts/{accountIDs}/historicalorders

        Args:
            account_ids: Account IDs (list or comma-separated string).
            since: Start date (inclusive) for the historical query.

        Returns:
            A list of historical order models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/historicalorders"
        raw = await self._transport.request("GET", path, params={"since": since.isoformat()})
        return parse_historical_orders_response(raw)

    async def get_historical_orders_by_id(
        self,
        account_ids: list[str] | str,
        order_ids: list[str] | str,
        *,
        since: date | None = None,
    ) -> list[HistoricalOrder]:
        """Fetch specific historical orders by order ID.

        Maps to: C8 GET /brokerage/accounts/{accountIDs}/historicalorders/{orderIDs}

        Args:
            account_ids: Account IDs (list or comma-separated string).
            order_ids: Order IDs (list or comma-separated string).
            since: Optional start date (inclusive) for the historical query.

        Returns:
            A list of historical order models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/historicalorders/{_join(order_ids)}"
        params = {"since": since.isoformat()} if since is not None else None
        raw = await self._transport.request("GET", path, params=params)
        return parse_historical_orders_response(raw)

    async def get_wallets(self, account_ids: list[str] | str) -> list[Wallet]:
        """Fetch crypto wallets for one or more accounts.

        Maps to: C9 GET /brokerage/accounts/{accountIDs}/wallets

        Args:
            account_ids: Account IDs (list or comma-separated string).

        Returns:
            A list of :class:`~tradestation.models.brokerage.Wallet` models.
        """
        path = f"/brokerage/accounts/{_join(account_ids)}/wallets"
        raw = await self._transport.request("GET", path)
        return parse_wallets_response(raw)

    # ------------------------------------------------------------------
    # C.2 — Streaming endpoints
    # ------------------------------------------------------------------

    async def stream_orders(
        self,
        account_ids: list[str],
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live order events for one or more accounts.

        Maps to: C10 GET /brokerage/stream/accounts/{accountIDs}/orders

        Args:
            account_ids: List of account IDs.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.
        """
        async for event in stream_events(
            self._transport,
            f"/brokerage/stream/accounts/{_join(account_ids)}/orders",
            include_heartbeats=include_heartbeats,
        ):
            yield event

    async def stream_orders_by_id(
        self,
        account_ids: list[str],
        order_ids: list[str],
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live events for specific orders.

        Maps to: C11 GET /brokerage/stream/accounts/{accountIDs}/orders/{orderIDs}

        Args:
            account_ids: List of account IDs.
            order_ids: List of order IDs.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.
        """
        async for event in stream_events(
            self._transport,
            f"/brokerage/stream/accounts/{_join(account_ids)}/orders/{_join(order_ids)}",
            include_heartbeats=include_heartbeats,
        ):
            yield event

    async def stream_positions(
        self,
        account_ids: list[str],
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live position updates for one or more accounts.

        Maps to: C12 GET /brokerage/stream/accounts/{accountIDs}/positions

        Args:
            account_ids: List of account IDs.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.
        """
        async for event in stream_events(
            self._transport,
            f"/brokerage/stream/accounts/{_join(account_ids)}/positions",
            include_heartbeats=include_heartbeats,
        ):
            yield event

    async def stream_wallets(
        self,
        account_ids: list[str],
        *,
        include_heartbeats: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Stream live wallet updates for one or more accounts.

        Maps to: C13 GET /brokerage/stream/accounts/{accountIDs}/wallets

        Args:
            account_ids: List of account IDs.
            include_heartbeats: When ``True``, yield heartbeat events.

        Yields:
            :class:`~tradestation.streaming.StreamEvent` subclass instances.
        """
        async for event in stream_events(
            self._transport,
            f"/brokerage/stream/accounts/{_join(account_ids)}/wallets",
            include_heartbeats=include_heartbeats,
        ):
            yield event
