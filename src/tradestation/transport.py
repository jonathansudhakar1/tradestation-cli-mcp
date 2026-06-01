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
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from tradestation.auth import AuthManager
from tradestation.credentials import Credentials
from tradestation.errors import (
    ApiError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    StreamError,
    TimeoutError,
    ValidationError,
)

_logger = logging.getLogger("tradestation")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 30.0
_STREAM_TIMEOUT = 70.0  # keep-alive interval (35s) x 2
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds
_BACKOFF_MAX = 30.0  # seconds
_JITTER_FACTOR = 0.25

# Endpoints that must NEVER be auto-retried (order placement safety)
# Matches both /v3/orderexecution/orders and /orderexecution/orders
_NO_RETRY_PATTERN = re.compile(
    r"(?i)(?:/v3)?/orderexecution/orders$",
    re.IGNORECASE,
)

# Verbs that are safe to retry
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# ---------------------------------------------------------------------------
# Redacting log filter
# ---------------------------------------------------------------------------

_REDACT_PATTERNS = [
    re.compile(r"(Authorization:\s*Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(client_secret=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(refresh_token=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(\"client_secret\"\s*:\s*\")[^\"]+\"", re.IGNORECASE),
    re.compile(r"(\"refresh_token\"\s*:\s*\")[^\"]+\"", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
]


class _RedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive values from log records.

    Scrubs Authorization headers, client_secret, and refresh_token from
    any log message at any level.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the message
        msg = record.getMessage()
        for pattern in _REDACT_PATTERNS:
            msg = pattern.sub(r"\g<1>[REDACTED]", msg)
        # Rebuild the record so formatters see the redacted string
        record.msg = msg
        record.args = ()
        return True


def _install_redacting_filter(logger: logging.Logger | None = None) -> None:
    """Idempotently attach the redacting filter to the tradestation logger."""
    target = logger or logging.getLogger("tradestation")
    for existing in target.filters:
        if isinstance(existing, _RedactingFilter):
            return
    target.addFilter(_RedactingFilter())


# Install on import — idempotent
_install_redacting_filter()


# ---------------------------------------------------------------------------
# Token-bucket rate limiter
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Simple token-bucket rate limiter for a single endpoint family."""

    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate  # tokens per second
        self._capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until *tokens* are available, then consume them."""
        while True:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return

            wait = (tokens - self._tokens) / self._rate
            await asyncio.sleep(wait)


# Per-family buckets: (rate tokens/sec, burst capacity)
_RATE_LIMIT_CONFIG: dict[str, tuple[float, float]] = {
    "marketdata": (10.0, 10.0),
    "brokerage": (5.0, 5.0),
    "orderexecution": (2.0, 5.0),
    "default": (10.0, 20.0),
}


def _endpoint_family(path: str) -> str:
    """Classify an API path into a rate-limit family."""
    lower = path.lower()
    if "marketdata" in lower:
        return "marketdata"
    if "brokerage" in lower:
        return "brokerage"
    if "orderexecution" in lower:
        return "orderexecution"
    return "default"


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


class Transport:
    """Low-level HTTP transport for the TradeStation v3 API.

    Args:
        credentials: Credential snapshot supplying the base URL and auth.
        timeout: Default request timeout in seconds. Default: 30.
        retries: Maximum retry attempts for idempotent requests. Default: 3.
        user_agent: User-Agent header value appended to the default.
        auth_manager: Optional pre-built AuthManager; constructed from
            *credentials* if not provided.
        http_client: Optional pre-built httpx.AsyncClient for testing.
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        retries: int = _MAX_RETRIES,
        user_agent: str = "",
        auth_manager: AuthManager | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._credentials = credentials
        self._base_url = credentials.base_url
        self._timeout = timeout
        self._retries = retries
        self._user_agent = user_agent

        self._auth = auth_manager or AuthManager(credentials)
        self._own_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

        # One bucket per endpoint family, created lazily
        self._buckets: dict[str, _TokenBucket] = {
            family: _TokenBucket(rate, burst)
            for family, (rate, burst) in _RATE_LIMIT_CONFIG.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
            path: API path relative to the base URL (e.g. ``/marketdata/quotes/AAPL``).
            params: Query-string parameters.
            json: Request body to serialise as JSON.
            headers: Extra headers merged into the request (Authorization is set
                automatically).

        Returns:
            Decoded JSON response as a plain dict.

        Raises:
            tradestation.errors.RateLimitError: On HTTP 429.
            tradestation.errors.ApiError: On HTTP 4xx / 5xx.
            tradestation.errors.NetworkError: On transport failure.
            tradestation.errors.TimeoutError: On request timeout.

        See docs/05-python-library.md §"Concurrency, rate limiting, retries".
        """
        url = self._base_url + path
        family = _endpoint_family(path)
        bucket = self._buckets[family]
        never_retry = bool(_NO_RETRY_PATTERN.search(path))
        method_upper = method.upper()

        last_exc: Exception | None = None
        attempts = self._retries + 1

        for attempt in range(attempts):
            # Rate-limit
            await bucket.acquire()

            # Auth header
            token = await self._auth.ensure_fresh()
            merged_headers = {"Authorization": f"Bearer {token}"}
            if self._user_agent:
                merged_headers["User-Agent"] = self._user_agent
            if headers:
                merged_headers.update(headers)

            _logger.debug("→ %s %s (attempt %d)", method_upper, path, attempt + 1)

            try:
                response = await self._client.request(
                    method_upper,
                    url,
                    params=params,
                    json=json,
                    headers=merged_headers,
                    timeout=self._timeout,
                )
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(f"Request timed out: {method_upper} {path}", status=None)
                if (
                    never_retry
                    or method_upper not in _IDEMPOTENT_METHODS
                    or attempt >= self._retries
                ):
                    raise last_exc from exc
                await self._backoff(attempt)
                continue
            except httpx.ConnectError as exc:
                last_exc = NetworkError(
                    f"Connection error: {method_upper} {path}: {exc}", status=None
                )
                if (
                    never_retry
                    or method_upper not in _IDEMPOTENT_METHODS
                    or attempt >= self._retries
                ):
                    raise last_exc from exc
                await self._backoff(attempt)
                continue
            except httpx.RequestError as exc:
                last_exc = NetworkError(f"Request error: {method_upper} {path}: {exc}", status=None)
                if (
                    never_retry
                    or method_upper not in _IDEMPOTENT_METHODS
                    or attempt >= self._retries
                ):
                    raise last_exc from exc
                await self._backoff(attempt)
                continue

            status = response.status_code
            request_id = response.headers.get("X-Request-Id")

            _logger.debug("← %d %s %s", status, method_upper, path)

            # 429 — rate limited
            if status == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                rate_err = RateLimitError(
                    f"Rate limited on {method_upper} {path}",
                    retry_after=retry_after,
                    request_id=request_id,
                )
                if (
                    never_retry
                    or method_upper not in _IDEMPOTENT_METHODS
                    or attempt >= self._retries
                ):
                    raise rate_err
                wait = retry_after if retry_after is not None else self._backoff_seconds(attempt)
                _logger.debug("Rate limited; waiting %.1fs before retry", wait)
                await asyncio.sleep(wait)
                last_exc = rate_err
                continue

            # 5xx — server errors (retry idempotent)
            if status >= 500:
                try:
                    payload: dict[str, Any] = response.json()
                except Exception:
                    payload = {}
                srv_err = ServerError(
                    f"Server error {status} on {method_upper} {path}",
                    status=status,
                    request_id=request_id,
                    payload=payload,
                )
                if (
                    never_retry
                    or method_upper not in _IDEMPOTENT_METHODS
                    or attempt >= self._retries
                ):
                    raise srv_err
                await self._backoff(attempt)
                last_exc = srv_err
                continue

            # 4xx — client errors (never retry)
            if status >= 400:
                try:
                    err_payload: dict[str, Any] = response.json()
                except Exception:
                    err_payload = {}
                raise _build_api_error(status, method_upper, path, request_id, err_payload)

            # Success
            try:
                return response.json()  # type: ignore[no-any-return]
            except Exception as exc:
                raise ApiError(
                    f"Invalid JSON response from {method_upper} {path}",
                    status=status,
                    request_id=request_id,
                ) from exc

        # Should not reach here
        if last_exc is not None:
            raise last_exc
        raise NetworkError(f"All {attempts} attempts failed for {method_upper} {path}")

    async def request_stream(
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
        return self._stream_iter(path, params=params)

    async def stream(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        """Alias for :meth:`request_stream` (backward compat)."""
        return self._stream_iter(path, params=params)

    async def close(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` and release connections."""
        if self._own_client:
            await self._client.aclose()
            _logger.debug("Transport HTTP client closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _stream_iter(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        url = self._base_url + path
        token = await self._auth.ensure_fresh()
        merged_headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
        if self._user_agent:
            merged_headers["User-Agent"] = self._user_agent

        _logger.debug("→ STREAM GET %s", path)

        try:
            async with self._client.stream(
                "GET",
                url,
                params=params,
                headers=merged_headers,
                timeout=httpx.Timeout(_STREAM_TIMEOUT),
            ) as response:
                if response.status_code != 200:
                    request_id = response.headers.get("X-Request-Id")
                    try:
                        err_payload: dict[str, Any] = response.json()
                    except Exception:
                        err_payload = {}
                    raise StreamError(
                        f"Stream endpoint returned HTTP {response.status_code}",
                        stream_url=url,
                        status=response.status_code,
                        request_id=request_id,
                        payload=err_payload,
                    )

                _logger.debug("← STREAM 200 %s", path)
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line:
                        yield line.encode()
        except httpx.TimeoutException as exc:
            raise StreamError(
                f"Stream timed out: {path}",
                stream_url=url,
            ) from exc
        except httpx.RequestError as exc:
            raise StreamError(
                f"Stream connection error: {path}: {exc}",
                stream_url=url,
            ) from exc
        except StreamError:
            raise
        except Exception as exc:
            raise StreamError(
                f"Unexpected stream error on {path}: {exc}",
                stream_url=url,
            ) from exc

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        """Calculate exponential backoff with jitter."""
        base: float = _BACKOFF_BASE * (2**attempt)
        jitter: float = random.uniform(-_JITTER_FACTOR * base, _JITTER_FACTOR * base)
        result: float = min(base + jitter, _BACKOFF_MAX)
        return result

    async def _backoff(self, attempt: int) -> None:
        """Sleep for the appropriate backoff duration."""
        wait = self._backoff_seconds(attempt)
        _logger.debug("Retrying after %.2fs (attempt %d)", wait, attempt + 1)
        await asyncio.sleep(wait)


# ---------------------------------------------------------------------------
# Error-building helpers
# ---------------------------------------------------------------------------


def _build_api_error(
    status: int,
    method: str,
    path: str,
    request_id: str | None,
    payload: dict[str, Any],
) -> ApiError:
    """Map an HTTP error status to the appropriate ApiError subclass."""
    msg = f"HTTP {status} on {method} {path}"
    if status == 400:
        return ValidationError(msg, status=status, request_id=request_id, payload=payload)
    if status == 404:
        return NotFoundError(msg, status=status, request_id=request_id, payload=payload)
    if status >= 500:
        return ServerError(msg, status=status, request_id=request_id, payload=payload)
    return ApiError(msg, status=status, request_id=request_id, payload=payload)


def _parse_retry_after(header_value: str | None) -> float | None:
    """Parse the ``Retry-After`` header value into seconds."""
    if header_value is None:
        return None
    try:
        return float(header_value)
    except ValueError:
        pass
    # Try HTTP-date format
    from datetime import datetime as _datetime
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(header_value)
        now = _datetime.now(tz=dt.tzinfo)
        delta_secs: float = (dt - now).total_seconds()
        return max(0.0, delta_secs)
    except Exception:
        return None
