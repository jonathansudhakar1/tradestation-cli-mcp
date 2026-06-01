"""BrokerageService — all C-series endpoint methods.

See docs/03-endpoint-inventory.md §"C. Brokerage" for the full inventory.
See docs/05-python-library.md §"Service surface" for method signatures.

All methods raise ``NotImplementedError`` in Phase 0 (scaffolding only).
Implementation tracked in Phase 2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from tradestation.services.base import BaseService
from tradestation.streaming import StreamEvent


class BrokerageService(BaseService):
    """Service wrapping all TradeStation Brokerage v3 endpoints (C1-C13).

    Obtain via ``client.brokerage`` — do not construct directly.
    """

    # ------------------------------------------------------------------
    # C.1 — REST endpoints
    # ------------------------------------------------------------------

    async def list_accounts(self) -> Any:
        """List all brokerage accounts for the authenticated user.

        Maps to: C1 GET /brokerage/accounts

        Returns:
            Parsed account list (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C1")

    async def get_balances(self, account_ids: list[str]) -> Any:
        """Fetch real-time balances for one or more accounts.

        Maps to: C2 GET /brokerage/accounts/{accountIDs}/balances

        Args:
            account_ids: List of account IDs (joined as comma-separated path
                segment).

        Returns:
            Parsed balances response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C2")

    async def get_bod_balances(self, account_ids: list[str]) -> Any:
        """Fetch beginning-of-day balances for one or more accounts.

        Maps to: C3 GET /brokerage/accounts/{accountIDs}/balances/bod

        Args:
            account_ids: List of account IDs.

        Returns:
            Parsed BOD balances response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C3")

    async def get_positions(self, account_ids: list[str]) -> Any:
        """Fetch open positions for one or more accounts.

        Maps to: C4 GET /brokerage/accounts/{accountIDs}/positions

        Args:
            account_ids: List of account IDs.

        Returns:
            Parsed positions response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C4")

    async def get_orders(self, account_ids: list[str]) -> Any:
        """Fetch today's orders for one or more accounts.

        Maps to: C5 GET /brokerage/accounts/{accountIDs}/orders

        Args:
            account_ids: List of account IDs.

        Returns:
            Parsed orders response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C5")

    async def get_orders_by_id(
        self,
        account_ids: list[str],
        order_ids: list[str],
    ) -> Any:
        """Fetch specific orders by order ID.

        Maps to: C6 GET /brokerage/accounts/{accountIDs}/orders/{orderIDs}

        Args:
            account_ids: List of account IDs.
            order_ids: List of order IDs.

        Returns:
            Parsed orders response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C6")

    async def get_historical_orders(
        self,
        account_ids: list[str],
        since: date,
    ) -> Any:
        """Fetch historical orders since a given date.

        Maps to: C7 GET /brokerage/accounts/{accountIDs}/historicalorders

        Args:
            account_ids: List of account IDs.
            since: Start date (inclusive) for the historical query.

        Returns:
            Parsed historical orders response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C7")

    async def get_historical_orders_by_id(
        self,
        account_ids: list[str],
        order_ids: list[str],
    ) -> Any:
        """Fetch specific historical orders by order ID.

        Maps to: C8 GET /brokerage/accounts/{accountIDs}/historicalorders/{orderIDs}

        Args:
            account_ids: List of account IDs.
            order_ids: List of order IDs.

        Returns:
            Parsed historical orders response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C8")

    async def get_wallets(self, account_ids: list[str]) -> Any:
        """Fetch crypto wallets for one or more accounts.

        Maps to: C9 GET /brokerage/accounts/{accountIDs}/wallets

        Args:
            account_ids: List of account IDs.

        Returns:
            Parsed wallets response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' C9")

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

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' C10")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

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

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' C11")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

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

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' C12")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover

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

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives' C13")
        yield StreamEvent()  # type: ignore[unreachable]  # pragma: no cover
