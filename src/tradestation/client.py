"""TradeStationClient — synchronous facade over the async core.

See docs/05-python-library.md §"Construction" for factory method signatures
and §"Design principles" for the sync-over-async rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio

from tradestation.credentials import Credentials, from_env, load
from tradestation.enums import Environment
from tradestation.services.brokerage import BrokerageService
from tradestation.services.market_data import MarketDataService
from tradestation.services.order_execution import OrderExecutionService
from tradestation.transport import Transport

if TYPE_CHECKING:
    from tradestation.async_client import AsyncTradeStationClient


class TradeStationClient:
    """Synchronous TradeStation API client.

    Wraps :class:`~tradestation.async_client.AsyncTradeStationClient` via
    ``anyio.from_thread`` so every service method is blocking and can be
    called from ordinary (non-async) Python.

    Prefer :class:`~tradestation.async_client.AsyncTradeStationClient` inside
    ``async def`` code for best performance.

    Examples::

        # Default credentials at ~/.tscli/credentials
        ts = TradeStationClient.from_default_credentials()

        # From environment variables
        ts = TradeStationClient.from_env()

        # Explicit credentials (CI / testing)
        from tradestation import Credentials, Environment

        ts = TradeStationClient(
            Credentials(
                client_id="...",
                client_secret="...",
                refresh_token="...",
                environment=Environment.SIM,
            )
        )
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        user_agent: str = "",
    ) -> None:
        """Create a client from an explicit :class:`~tradestation.credentials.Credentials`.

        Args:
            credentials: Credential snapshot.
            timeout: Default HTTP request timeout in seconds.
            retries: Maximum retries for idempotent requests.
            user_agent: Additional User-Agent suffix.
        """
        self._credentials = credentials
        self._timeout = timeout
        self._retries = retries
        self._user_agent = user_agent
        self._transport = Transport(
            credentials,
            timeout=timeout,
            retries=retries,
            user_agent=user_agent,
        )
        self._market_data: MarketDataService | None = None
        self._brokerage: BrokerageService | None = None
        self._order_execution: OrderExecutionService | None = None

    # ------------------------------------------------------------------
    # Class-method constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_default_credentials(
        cls,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        environment: Environment | None = None,
        user_agent: str = "",
    ) -> TradeStationClient:
        """Load credentials from ``~/.tscli/credentials`` and return a client.

        Args:
            timeout: Default HTTP request timeout in seconds.
            retries: Maximum retries for idempotent requests.
            environment: Override the environment stored in the credentials
                file (``live`` or ``sim``).
            user_agent: Additional User-Agent suffix.

        Raises:
            tradestation.errors.NoCredentialsError: If the credentials file
                does not exist.
        """
        creds = load()
        if environment is not None:
            creds = creds.replace(environment=environment)
        return cls(creds, timeout=timeout, retries=retries, user_agent=user_agent)

    @classmethod
    def from_env(
        cls,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        user_agent: str = "",
    ) -> TradeStationClient:
        """Build a client from environment variables.

        Reads ``TS_CLIENT_ID``, ``TS_CLIENT_SECRET`` (optional),
        ``TS_REFRESH_TOKEN``, ``TS_SCOPE`` (optional),
        ``TS_ENV`` (optional; default: ``sim``).

        Args:
            timeout: Default HTTP request timeout in seconds.
            retries: Maximum retries for idempotent requests.
            user_agent: Additional User-Agent suffix.

        Raises:
            tradestation.errors.NoCredentialsError: If any required variable
                is missing.
        """
        creds = from_env()
        return cls(creds, timeout=timeout, retries=retries, user_agent=user_agent)

    @classmethod
    def from_profile(
        cls,
        profile: str,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        user_agent: str = "",
    ) -> TradeStationClient:
        """Load credentials from a named profile at ``~/.tscli/profiles/<name>/``.

        Args:
            profile: Profile name (e.g. ``"paper"``).
            timeout: Default HTTP request timeout in seconds.
            retries: Maximum retries for idempotent requests.
            user_agent: Additional User-Agent suffix.

        Raises:
            tradestation.errors.NoCredentialsError: If the profile does not
                exist.
        """
        creds = load(profile=profile)
        return cls(creds, timeout=timeout, retries=retries, user_agent=user_agent)

    # ------------------------------------------------------------------
    # Service properties
    # ------------------------------------------------------------------

    @property
    def market_data(self) -> MarketDataService:
        """The MarketData service (B-series endpoints).

        Returns:
            :class:`~tradestation.services.market_data.MarketDataService`
        """
        if self._market_data is None:
            self._market_data = MarketDataService(self._transport)
        return self._market_data

    @property
    def brokerage(self) -> BrokerageService:
        """The Brokerage service (C-series endpoints).

        Returns:
            :class:`~tradestation.services.brokerage.BrokerageService`

        Raises:
            NotImplementedError: Until Phase 4 implementation.
        """
        if self._brokerage is None:
            self._brokerage = BrokerageService(self._transport)
        return self._brokerage

    @property
    def order_execution(self) -> OrderExecutionService:
        """The OrderExecution service (D-series endpoints).

        Returns:
            :class:`~tradestation.services.order_execution.OrderExecutionService`

        Raises:
            NotImplementedError: Until Phase 5 implementation.
        """
        if self._order_execution is None:
            self._order_execution = OrderExecutionService(self._transport)
        return self._order_execution

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Async bridge
    # ------------------------------------------------------------------

    def as_async(self) -> AsyncTradeStationClient:
        """Return an :class:`AsyncTradeStationClient` sharing these credentials.

        Useful for streaming from otherwise-synchronous code (e.g. the CLI),
        which must drive an ``async for`` loop::

            async with sync_client.as_async() as ts:
                async for event in ts.market_data.stream_quotes(["AAPL"]):
                    ...
        """
        from tradestation.async_client import AsyncTradeStationClient

        return AsyncTradeStationClient(
            self._credentials,
            timeout=self._timeout,
            retries=self._retries,
            user_agent=self._user_agent,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP transport and release resources."""
        anyio.run(self._transport.close)

    def __enter__(self) -> TradeStationClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
