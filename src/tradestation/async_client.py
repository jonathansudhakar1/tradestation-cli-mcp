"""AsyncTradeStationClient — native async client.

See docs/05-python-library.md §"Construction" and §"Design principles".
"""

from __future__ import annotations

from tradestation.credentials import Credentials, from_env, load
from tradestation.enums import Environment
from tradestation.services.brokerage import BrokerageService
from tradestation.services.market_data import MarketDataService
from tradestation.services.order_execution import OrderExecutionService
from tradestation.transport import Transport


class AsyncTradeStationClient:
    """Native async TradeStation API client.

    Use this inside ``async def`` code for best performance.  The synchronous
    :class:`~tradestation.client.TradeStationClient` wraps this class via
    ``anyio.from_thread``.

    Examples::

        async with AsyncTradeStationClient.from_default_credentials() as ts:
            quotes = await ts.market_data.get_quotes(["AAPL", "MSFT"])
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
    ) -> AsyncTradeStationClient:
        """Load credentials from ``~/.tscli/credentials`` and return a client.

        Args:
            timeout: Default HTTP request timeout in seconds.
            retries: Maximum retries for idempotent requests.
            environment: Override the environment stored in credentials.
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
    ) -> AsyncTradeStationClient:
        """Build a client from environment variables.

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
    ) -> AsyncTradeStationClient:
        """Load credentials from a named profile.

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
        """The MarketData service (B-series endpoints)."""
        if self._market_data is None:
            self._market_data = MarketDataService(self._transport)
        return self._market_data

    @property
    def brokerage(self) -> BrokerageService:
        """The Brokerage service (C-series endpoints)."""
        if self._brokerage is None:
            self._brokerage = BrokerageService(self._transport)
        return self._brokerage

    @property
    def order_execution(self) -> OrderExecutionService:
        """The OrderExecution service (D-series endpoints)."""
        if self._order_execution is None:
            self._order_execution = OrderExecutionService(self._transport)
        return self._order_execution

    # ------------------------------------------------------------------
    # Async context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncTradeStationClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP transport and release resources."""
        await self._transport.close()
