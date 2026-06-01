"""TradeStationClient — synchronous facade over the async core.

See docs/05-python-library.md §"Construction" for factory method signatures
and §"Design principles" for the sync-over-async rationale.

Implementation: Phase 2.  All methods raise ``NotImplementedError``.
"""

from __future__ import annotations

from tradestation.credentials import Credentials
from tradestation.enums import Environment
from tradestation.services.brokerage import BrokerageService
from tradestation.services.market_data import MarketDataService
from tradestation.services.order_execution import OrderExecutionService


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
    ) -> TradeStationClient:
        """Build a client from environment variables.

        Reads ``TS_CLIENT_ID``, ``TS_CLIENT_SECRET``, ``TS_REFRESH_TOKEN``,
        ``TS_SCOPE`` (optional), ``TS_ENV`` (optional; default: ``live``).

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
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Construction'")

    # ------------------------------------------------------------------
    # Service properties
    # ------------------------------------------------------------------

    @property
    def market_data(self) -> MarketDataService:
        """The MarketData service (B-series endpoints).

        Returns:
            :class:`~tradestation.services.market_data.MarketDataService`

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface'")

    @property
    def brokerage(self) -> BrokerageService:
        """The Brokerage service (C-series endpoints).

        Returns:
            :class:`~tradestation.services.brokerage.BrokerageService`

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface'")

    @property
    def order_execution(self) -> OrderExecutionService:
        """The OrderExecution service (D-series endpoints).

        Returns:
            :class:`~tradestation.services.order_execution.OrderExecutionService`

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface'")
