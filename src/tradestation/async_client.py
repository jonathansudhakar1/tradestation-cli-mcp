"""AsyncTradeStationClient — native async client.

See docs/05-python-library.md §"Construction" and §"Design principles".

Implementation: Phase 2.  All methods raise ``NotImplementedError``.
"""

from __future__ import annotations

from tradestation.credentials import Credentials
from tradestation.enums import Environment
from tradestation.services.brokerage import BrokerageService
from tradestation.services.market_data import MarketDataService
from tradestation.services.order_execution import OrderExecutionService


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
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Construction'")

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
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Construction'")

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
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Construction'")

    # ------------------------------------------------------------------
    # Service properties
    # ------------------------------------------------------------------

    @property
    def market_data(self) -> MarketDataService:
        """The MarketData service (B-series endpoints).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface'")

    @property
    def brokerage(self) -> BrokerageService:
        """The Brokerage service (C-series endpoints).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface'")

    @property
    def order_execution(self) -> OrderExecutionService:
        """The OrderExecution service (D-series endpoints).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface'")

    # ------------------------------------------------------------------
    # Async context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncTradeStationClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP transport and release resources."""
        raise NotImplementedError("see docs/05-python-library.md §'Concurrency'")
