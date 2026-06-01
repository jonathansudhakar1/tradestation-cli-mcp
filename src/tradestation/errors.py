"""Exception hierarchy for the tradestation library.

See docs/05-python-library.md §"Errors" for the full design.

Hierarchy:
    TradeStationError
    ├── AuthError
    │   ├── NoCredentialsError
    │   └── RefreshTokenExpired
    ├── NetworkError
    │   ├── TimeoutError
    │   └── ConnectionResetError
    ├── RateLimitError
    ├── ApiError                  (4xx with TS body)
    │   ├── ValidationError       (400 with field-level messages)
    │   ├── NotFoundError         (404)
    │   └── ServerError           (5xx)
    ├── OrderRejectedError        (D-series rejections)
    └── StreamError               (mid-stream failure)
"""

from __future__ import annotations


class TradeStationError(Exception):
    """Base class for all tradestation library errors."""

    def __init__(
        self,
        message: str,
        *,
        request_id: str | None = None,
        status: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.status = status
        self.payload = payload

    def human_message(self) -> str:
        """Return a human-readable message suitable for CLI display."""
        return str(self)


# ---------------------------------------------------------------------------
# Auth errors
# ---------------------------------------------------------------------------


class AuthError(TradeStationError):
    """Authentication or authorisation failure."""


class NoCredentialsError(AuthError):
    """No credentials found at ~/.tscli/credentials (or TS_CREDENTIALS path).

    Hint: run ``ts auth set`` to configure credentials.
    """


class RefreshTokenExpired(AuthError):
    """The refresh token was rejected by TradeStation's token endpoint.

    Hint: run ``ts auth login`` or supply a new refresh token via
    ``ts auth set --refresh-token …``.
    """

    def human_message(self) -> str:
        return (
            "Refresh token rejected (invalid_grant). "
            "Run `ts auth login` to obtain a new refresh token, "
            "or supply one via `ts auth set --refresh-token …`."
        )


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


class NetworkError(TradeStationError):
    """A transport-level failure (no HTTP response received)."""


class TimeoutError(NetworkError):
    """The request timed out before a response was received."""


class ConnectionResetError(NetworkError):
    """The connection was reset by the remote server."""


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class RateLimitError(TradeStationError):
    """HTTP 429 — the rate-limit bucket was exhausted.

    ``retry_after`` is the number of seconds to wait before retrying, parsed
    from the ``Retry-After`` response header when present.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        request_id: str | None = None,
        status: int | None = 429,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id, status=status, payload=payload)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# API errors (4xx / 5xx with a TS error body)
# ---------------------------------------------------------------------------


class ApiError(TradeStationError):
    """An HTTP error response was received from the TradeStation API.

    Attributes:
        status: HTTP status code.
        payload: Decoded JSON body from TradeStation (may be None on parse failure).
        request_id: Value of the ``X-Request-Id`` response header.
    """


class ValidationError(ApiError):
    """HTTP 400 — the request body failed field-level validation.

    ``field_errors`` is a mapping of field name → list of error messages,
    when TradeStation provides per-field detail.
    """

    def __init__(
        self,
        message: str,
        *,
        field_errors: dict[str, list[str]] | None = None,
        request_id: str | None = None,
        status: int | None = 400,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id, status=status, payload=payload)
        self.field_errors: dict[str, list[str]] = field_errors or {}


class NotFoundError(ApiError):
    """HTTP 404 — the requested resource was not found."""


class ServerError(ApiError):
    """HTTP 5xx — a server-side error occurred at TradeStation."""


# ---------------------------------------------------------------------------
# Order errors
# ---------------------------------------------------------------------------


class OrderRejectedError(TradeStationError):
    """An order or order-group submission was rejected by TradeStation.

    This is distinct from a generic ``ApiError`` because TradeStation may
    return HTTP 200 with a rejection payload in the body (D-series endpoints).

    ``order_id`` is present when the rejection is for a specific order.
    ``reason`` is the raw rejection message from TradeStation.
    """

    def __init__(
        self,
        message: str,
        *,
        order_id: str | None = None,
        reason: str | None = None,
        request_id: str | None = None,
        status: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id, status=status, payload=payload)
        self.order_id = order_id
        self.reason = reason

    def human_message(self) -> str:
        parts = ["Order rejected"]
        if self.order_id:
            parts.append(f"(order {self.order_id})")
        if self.reason:
            parts.append(f": {self.reason}")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Streaming errors
# ---------------------------------------------------------------------------


class StreamError(TradeStationError):
    """A mid-stream error frame was received, or the connection was lost.

    ``stream_url`` is the endpoint URL that was being streamed.
    Catch this and call the stream method again to reconnect (up to
    ``max_reconnects``).
    """

    def __init__(
        self,
        message: str,
        *,
        stream_url: str | None = None,
        request_id: str | None = None,
        status: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id, status=status, payload=payload)
        self.stream_url = stream_url


class StreamHeartbeat(Exception):
    """Raised (or yielded) when a heartbeat frame is received from a stream.

    Not an error — raised as a sentinel when ``include_heartbeats=True`` so
    callers can distinguish data events from keep-alive pings.
    """

    def __init__(self, raw: dict[str, object] | None = None) -> None:
        super().__init__("heartbeat")
        self.raw = raw
