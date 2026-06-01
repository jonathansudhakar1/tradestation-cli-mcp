"""Transport — httpx-based HTTP client with retries, rate limiting, and logging.

See docs/05-python-library.md §"Concurrency, rate limiting, retries" and
docs/02-auth-and-credentials.md §"Logging" for the full design.

Responsibilities:
- Wraps ``httpx.AsyncClient`` (one per ``AsyncTradeStationClient``).
- Calls ``AuthManager.ensure_fresh()`` before each authenticated request.
- Applies a per-endpoint-family token-bucket rate limiter.
- Retries idempotent verbs with exponential backoff + jitter.
- Parses ``Retry-After`` on 429 responses.
- Strips ``Authorization``, ``client_secret``, ``refresh_token`` from all logs.
- Streams chunked-transfer endpoints as raw ``AsyncIterator[bytes]``.

Implementation: Phase 2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from tradestation.credentials import Credentials


class Transport:
    """Low-level HTTP transport for the TradeStation v3 API.

    Args:
        credentials: Credential snapshot supplying the base URL and auth.
        timeout: Default request timeout in seconds. Default: 30.
        retries: Maximum retry attempts for idempotent requests. Default: 3.
        user_agent: User-Agent header value appended to the default.
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        user_agent: str = "",
    ) -> None:
        self._credentials = credentials
        self._timeout = timeout
        self._retries = retries
        self._user_agent = user_agent

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an authenticated HTTP request and return the decoded JSON body.

        Args:
            method: HTTP verb (``GET``, ``POST``, ``PUT``, ``DELETE``).
            path: API path relative to the base URL
                (e.g. ``/marketdata/quotes/AAPL``).
            params: Query-string parameters.
            json: Request body to serialise as JSON.
            headers: Extra headers to merge (``Authorization`` is set
                automatically).

        Returns:
            Decoded JSON response as a plain dict.

        Raises:
            tradestation.errors.RateLimitError: On HTTP 429.
            tradestation.errors.ApiError: On HTTP 4xx / 5xx.
            tradestation.errors.NetworkError: On transport failure.

        See docs/05-python-library.md §"Concurrency, rate limiting, retries".
        """
        raise NotImplementedError(
            "see docs/05-python-library.md §'Concurrency, rate limiting, retries'"
        )

    async def stream(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        """Open a chunked-transfer streaming connection and yield raw lines.

        Each yielded ``bytes`` value is one newline-delimited JSON frame from
        the stream (heartbeats included; callers filter them).

        Args:
            path: API path for the streaming endpoint.
            params: Query-string parameters.

        Yields:
            Raw UTF-8 bytes for each newline-delimited frame.

        Raises:
            tradestation.errors.StreamError: On mid-stream failure or disconnect.

        See docs/05-python-library.md §"Streaming primitives".
        """
        raise NotImplementedError("see docs/05-python-library.md §'Streaming primitives'")
        yield b""  # type: ignore[unreachable]  # pragma: no cover

    async def close(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` and release connections."""
        raise NotImplementedError("see docs/05-python-library.md §'Concurrency'")
