"""Unit tests for tradestation.transport.

Tests:
    - auth header injection
    - redaction filter actually redacts secrets
    - rate-limit backoff on 429
    - Retry-After header parsing
    - NEVER retry POST /v3/orderexecution/orders
    - retry on 5xx (idempotent)
    - retry on connection error (idempotent)
    - timeout error on GET
    - 4xx → ApiError (400, 404, 403)
    - streaming: yields lines
    - streaming: raises StreamError on non-200
    - endpoint family classification
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from tradestation.auth import AuthManager
from tradestation.credentials import Credentials
from tradestation.enums import Environment
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
from tradestation.transport import (
    Transport,
    _build_api_error,
    _endpoint_family,
    _parse_retry_after,
    _RedactingFilter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creds() -> Credentials:
    return Credentials(
        client_id="cid",
        client_secret="csec",
        refresh_token="rt",
        environment=Environment.SIM,
    )


def _make_auth_manager(token: str = "test-bearer-token") -> AuthManager:
    """Return an AuthManager that always returns a fixed token."""
    creds = _make_creds()
    mgr = AuthManager(creds)
    mgr._access_token = token
    mgr._expires_at = float("inf")  # never expires
    return mgr


_BASE_URL = "https://sim-api.tradestation.com/v3"


# ---------------------------------------------------------------------------
# Redaction filter
# ---------------------------------------------------------------------------


class TestRedactingFilter:
    def _make_record(self, msg: str) -> logging.LogRecord:
        record = logging.LogRecord(
            name="tradestation",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        return record

    def test_redacts_bearer_token(self) -> None:
        filt = _RedactingFilter()
        record = self._make_record("Authorization: Bearer supersecrettoken123")
        filt.filter(record)
        assert "supersecrettoken123" not in record.getMessage()
        assert "REDACTED" in record.getMessage()

    def test_redacts_client_secret_in_form(self) -> None:
        filt = _RedactingFilter()
        record = self._make_record("client_secret=my-very-secret-value&grant_type=refresh_token")
        filt.filter(record)
        msg = record.getMessage()
        assert "my-very-secret-value" not in msg
        assert "REDACTED" in msg

    def test_redacts_refresh_token_in_form(self) -> None:
        filt = _RedactingFilter()
        record = self._make_record("refresh_token=super-long-refresh-token&client_id=foo")
        filt.filter(record)
        msg = record.getMessage()
        assert "super-long-refresh-token" not in msg

    def test_redacts_json_client_secret(self) -> None:
        filt = _RedactingFilter()
        record = self._make_record('{"client_secret": "hidden-secret-value"}')
        filt.filter(record)
        msg = record.getMessage()
        assert "hidden-secret-value" not in msg

    def test_safe_message_unchanged(self) -> None:
        filt = _RedactingFilter()
        msg = "GET /v3/marketdata/quotes/AAPL 200 OK"
        record = self._make_record(msg)
        filt.filter(record)
        assert record.getMessage() == msg

    def test_filter_installed_on_logger(self) -> None:
        """The redacting filter should be installed automatically on import."""

        logger = logging.getLogger("tradestation")
        filter_types = [type(f) for f in logger.filters]
        assert _RedactingFilter in filter_types

    def test_install_idempotent(self) -> None:
        """Installing the filter twice should not add duplicates."""
        from tradestation.transport import _install_redacting_filter

        logger = logging.getLogger("tradestation")
        before_count = sum(1 for f in logger.filters if isinstance(f, _RedactingFilter))
        _install_redacting_filter(logger)
        _install_redacting_filter(logger)
        after_count = sum(1 for f in logger.filters if isinstance(f, _RedactingFilter))
        assert after_count == before_count


# ---------------------------------------------------------------------------
# Endpoint family classification
# ---------------------------------------------------------------------------


class TestEndpointFamily:
    def test_marketdata(self) -> None:
        assert _endpoint_family("/v3/marketdata/quotes/AAPL") == "marketdata"

    def test_brokerage(self) -> None:
        assert _endpoint_family("/v3/brokerage/accounts") == "brokerage"

    def test_orderexecution(self) -> None:
        assert _endpoint_family("/v3/orderexecution/orders") == "orderexecution"

    def test_default(self) -> None:
        assert _endpoint_family("/v3/unknown/resource") == "default"


# ---------------------------------------------------------------------------
# Retry-After parsing
# ---------------------------------------------------------------------------


class TestParseRetryAfter:
    def test_integer_seconds(self) -> None:
        assert _parse_retry_after("30") == 30.0

    def test_float_seconds(self) -> None:
        assert _parse_retry_after("1.5") == 1.5

    def test_none(self) -> None:
        assert _parse_retry_after(None) is None

    def test_invalid_string(self) -> None:
        # Invalid date → None
        assert _parse_retry_after("not-a-date-or-number") is None


# ---------------------------------------------------------------------------
# _build_api_error
# ---------------------------------------------------------------------------


class TestBuildApiError:
    def test_400_validation(self) -> None:
        err = _build_api_error(400, "POST", "/v3/orders", None, {})
        assert isinstance(err, ValidationError)

    def test_404_not_found(self) -> None:
        err = _build_api_error(404, "GET", "/v3/thing", None, {})
        assert isinstance(err, NotFoundError)

    def test_500_server(self) -> None:
        err = _build_api_error(500, "GET", "/v3/thing", None, {})
        assert isinstance(err, ServerError)

    def test_403_api_error(self) -> None:
        err = _build_api_error(403, "GET", "/v3/thing", None, {})
        assert isinstance(err, ApiError)
        assert not isinstance(err, ValidationError)
        assert not isinstance(err, NotFoundError)


# ---------------------------------------------------------------------------
# Transport.request — auth header injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthHeaderInjection:
    @respx.mock
    async def test_bearer_token_in_request(self) -> None:
        route = respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(200, json={"Quotes": []})
        )
        auth_mgr = _make_auth_manager("test-bearer-token")
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            await transport.request("GET", "/marketdata/quotes/AAPL")
        finally:
            await transport.close()

        assert route.called
        req = route.calls.last.request
        assert req.headers["Authorization"] == "Bearer test-bearer-token"

    @respx.mock
    async def test_custom_user_agent_included(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            return_value=httpx.Response(200, json={})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(
            _make_creds(), auth_manager=auth_mgr, user_agent="mybot/1.0", retries=0
        )
        try:
            await transport.request("GET", "/marketdata/quotes/X")
        finally:
            await transport.close()


# ---------------------------------------------------------------------------
# Transport.request — 4xx errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestApiErrors:
    @respx.mock
    async def test_400_raises_validation_error(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            return_value=httpx.Response(400, json={"Message": "Bad request"})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(ValidationError) as exc_info:
                await transport.request("GET", "/marketdata/quotes/X")
            assert exc_info.value.status == 400
        finally:
            await transport.close()

    @respx.mock
    async def test_404_raises_not_found(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            return_value=httpx.Response(404, json={"Message": "Not found"})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(NotFoundError):
                await transport.request("GET", "/marketdata/quotes/X")
        finally:
            await transport.close()

    @respx.mock
    async def test_403_raises_api_error(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            return_value=httpx.Response(403, json={"Message": "Forbidden"})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(ApiError):
                await transport.request("GET", "/marketdata/quotes/X")
        finally:
            await transport.close()


# ---------------------------------------------------------------------------
# Transport.request — 5xx retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRetries:
    @respx.mock
    async def test_5xx_retried_on_get(self) -> None:
        # First two calls 503, third 200
        route = respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.Response(503, json={"error": "Service Unavailable"}),
                httpx.Response(503, json={"error": "Service Unavailable"}),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=3, timeout=5.0)
        try:
            # Patch the backoff to avoid slow tests
            with patch.object(transport, "_backoff", new=AsyncMock()):
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            assert route.call_count == 3
        finally:
            await transport.close()

    @respx.mock
    async def test_5xx_raises_after_all_retries(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2, timeout=5.0)
        try:
            with patch.object(transport, "_backoff", new=AsyncMock()), pytest.raises(ServerError):
                await transport.request("GET", "/marketdata/quotes/AAPL")
        finally:
            await transport.close()

    @respx.mock
    async def test_5xx_not_retried_on_post(self) -> None:
        """POST requests should NOT be retried on 5xx (not idempotent)."""
        route = respx.post(f"{_BASE_URL}/brokerage/orders").mock(
            return_value=httpx.Response(500, json={"error": "Server Error"})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=3, timeout=5.0)
        try:
            with pytest.raises(ServerError):
                await transport.request("POST", "/brokerage/orders", json={})
            # Should only call once (no retries)
            assert route.call_count == 1
        finally:
            await transport.close()


# ---------------------------------------------------------------------------
# Transport.request — 429 rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRateLimitHandling:
    @respx.mock
    async def test_429_raises_rate_limit_error_when_retries_exhausted(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "5"}, json={})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(RateLimitError) as exc_info:
                await transport.request("GET", "/marketdata/quotes/AAPL")
            assert exc_info.value.retry_after == 5.0
        finally:
            await transport.close()

    @respx.mock
    async def test_429_then_success(self) -> None:
        route = respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}, json={}),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2)
        try:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            assert route.call_count == 2
        finally:
            await transport.close()


# ---------------------------------------------------------------------------
# ORDER PLACEMENT: NEVER retry POST /v3/orderexecution/orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderPlacementNoRetry:
    @respx.mock
    async def test_post_order_no_retry_on_5xx(self) -> None:
        route = respx.post(f"{_BASE_URL}/orderexecution/orders").mock(
            return_value=httpx.Response(503, json={"error": "Server Error"})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=3)
        try:
            with pytest.raises(ServerError):
                await transport.request(
                    "POST",
                    "/orderexecution/orders",
                    json={"Symbol": "AAPL"},
                )
            # MUST only be called exactly once — no retries
            assert route.call_count == 1
        finally:
            await transport.close()

    @respx.mock
    async def test_post_order_no_retry_on_timeout(self) -> None:
        route = respx.post(f"{_BASE_URL}/orderexecution/orders").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=3)
        try:
            with pytest.raises(TimeoutError):
                await transport.request("POST", "/orderexecution/orders", json={})
            assert route.call_count == 1
        finally:
            await transport.close()

    @respx.mock
    async def test_post_order_no_retry_on_429(self) -> None:
        route = respx.post(f"{_BASE_URL}/orderexecution/orders").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "1"}, json={})
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=3)
        try:
            with pytest.raises(RateLimitError):
                await transport.request("POST", "/orderexecution/orders", json={})
            assert route.call_count == 1
        finally:
            await transport.close()


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNetworkErrors:
    @respx.mock
    async def test_connect_error_raises_network_error(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            side_effect=httpx.ConnectError("refused")
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(NetworkError):
                await transport.request("GET", "/marketdata/quotes/X")
        finally:
            await transport.close()

    @respx.mock
    async def test_timeout_raises_timeout_error(self) -> None:
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(TimeoutError):
                await transport.request("GET", "/marketdata/quotes/X")
        finally:
            await transport.close()

    @respx.mock
    async def test_connect_error_retried_on_get(self) -> None:
        route = respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.ConnectError("refused"),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2)
        try:
            with patch.object(transport, "_backoff", new=AsyncMock()):
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            assert route.call_count == 2
        finally:
            await transport.close()


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStreaming:
    async def test_stream_yields_lines(self) -> None:
        """Transport.stream() should yield NDJSON lines as bytes."""
        lines = [
            b'{"Symbol":"AAPL","Last":"150.00","Type":"Quote"}',
            b'{"Type":"Heartbeat"}',
        ]
        auth_mgr = _make_auth_manager()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # Build a fake async context manager for client.stream()
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {}

        async def _aiter_lines() -> AsyncIterator[str]:
            for line in lines:
                yield line.decode()

        fake_response.aiter_lines = _aiter_lines

        class _FakeStreamCtx:
            async def __aenter__(self) -> MagicMock:
                return fake_response

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_client.stream.return_value = _FakeStreamCtx()

        transport = Transport(
            _make_creds(),
            auth_manager=auth_mgr,
            http_client=mock_client,
        )
        collected: list[bytes] = []
        # request_stream returns an async iterator
        stream_iter = await transport.request_stream("/marketdata/stream/quotes/AAPL")
        async for chunk in stream_iter:
            collected.append(chunk)

        assert len(collected) == 2
        assert collected[0] == lines[0]
        assert collected[1] == lines[1]

    async def test_stream_non_200_raises_stream_error(self) -> None:
        auth_mgr = _make_auth_manager()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        fake_response = MagicMock()
        fake_response.status_code = 401
        fake_response.headers = {}

        def _fake_json() -> dict[str, str]:
            return {"Message": "Unauthorized"}

        fake_response.json = _fake_json

        class _FakeStreamCtx:
            async def __aenter__(self) -> MagicMock:
                return fake_response

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_client.stream.return_value = _FakeStreamCtx()

        transport = Transport(
            _make_creds(),
            auth_manager=auth_mgr,
            http_client=mock_client,
        )
        with pytest.raises(StreamError) as exc_info:
            stream_iter = await transport.request_stream("/marketdata/stream/quotes/AAPL")
            async for _ in stream_iter:
                pass

        assert exc_info.value.status == 401


# ---------------------------------------------------------------------------
# Transport.close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTransportClose:
    async def test_close_is_idempotent(self) -> None:
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr)
        await transport.close()
        # Second close should not raise
        await transport.close()

    async def test_close_with_injected_client_does_not_close_it(self) -> None:
        """When an external client is injected, close() should not close it."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, http_client=mock_client)
        await transport.close()
        mock_client.aclose.assert_not_called()


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdditionalCoverage:
    @respx.mock
    async def test_request_id_in_error_payload(self) -> None:
        """X-Request-Id header should be captured in error."""
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            return_value=httpx.Response(
                404,
                json={"Message": "Symbol not found"},
                headers={"X-Request-Id": "req-abc-123"},
            )
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(NotFoundError) as exc_info:
                await transport.request("GET", "/marketdata/quotes/X")
            assert exc_info.value.request_id == "req-abc-123"
        finally:
            await transport.close()

    @respx.mock
    async def test_generic_request_error_raises_network_error(self) -> None:
        """Generic httpx.RequestError (not ConnectError) raises NetworkError."""
        respx.get(f"{_BASE_URL}/marketdata/quotes/X").mock(
            side_effect=httpx.RequestError("generic error")
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            with pytest.raises(NetworkError):
                await transport.request("GET", "/marketdata/quotes/X")
        finally:
            await transport.close()

    @respx.mock
    async def test_retry_after_honored_on_429(self) -> None:
        """Transport waits Retry-After seconds before retrying 429."""
        respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "2"}, json={}),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2)
        try:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            # asyncio.sleep should have been called with 2.0 (Retry-After value)
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert 2.0 in sleep_calls
        finally:
            await transport.close()

    @respx.mock
    async def test_stream_with_user_agent(self) -> None:
        """User-Agent header should be set in stream requests."""
        auth_mgr = _make_auth_manager()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {}

        async def _aiter_lines() -> AsyncIterator[str]:
            return
            yield  # make this a generator

        fake_response.aiter_lines = _aiter_lines

        class _FakeStreamCtx:
            async def __aenter__(self) -> MagicMock:
                return fake_response

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_client.stream.return_value = _FakeStreamCtx()

        transport = Transport(
            _make_creds(),
            auth_manager=auth_mgr,
            http_client=mock_client,
            user_agent="testbot/1.0",
        )
        collected: list[bytes] = []
        stream_iter = await transport.stream("/marketdata/stream/quotes/AAPL")
        async for chunk in stream_iter:
            collected.append(chunk)

        # Verify User-Agent was passed
        call_kwargs = mock_client.stream.call_args[1]
        assert call_kwargs["headers"]["User-Agent"] == "testbot/1.0"

    @respx.mock
    async def test_stream_timeout_raises_stream_error(self) -> None:
        """Stream timeout (httpx.TimeoutException) should raise StreamError."""
        auth_mgr = _make_auth_manager()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        class _FakeStreamCtx:
            async def __aenter__(self) -> None:
                raise httpx.TimeoutException("stream timeout")

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_client.stream.return_value = _FakeStreamCtx()

        transport = Transport(
            _make_creds(),
            auth_manager=auth_mgr,
            http_client=mock_client,
        )
        with pytest.raises(StreamError):
            stream_iter = await transport.stream("/marketdata/stream/quotes/AAPL")
            async for _ in stream_iter:
                pass

    @respx.mock
    async def test_stream_request_error_raises_stream_error(self) -> None:
        """Stream request error should raise StreamError."""
        auth_mgr = _make_auth_manager()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        class _FakeStreamCtx:
            async def __aenter__(self) -> None:
                raise httpx.ConnectError("connection refused")

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_client.stream.return_value = _FakeStreamCtx()

        transport = Transport(
            _make_creds(),
            auth_manager=auth_mgr,
            http_client=mock_client,
        )
        with pytest.raises(StreamError):
            stream_iter = await transport.stream("/marketdata/stream/quotes/AAPL")
            async for _ in stream_iter:
                pass

    @respx.mock
    async def test_success_response_with_request_id(self) -> None:
        """Successful response captures X-Request-Id."""
        respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            return_value=httpx.Response(
                200,
                json={"Quotes": []},
                headers={"X-Request-Id": "req-xyz"},
            )
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=0)
        try:
            result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
        finally:
            await transport.close()

    @respx.mock
    async def test_generic_request_error_retried_on_get(self) -> None:
        """Generic httpx.RequestError on GET should be retried."""
        route = respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.RequestError("transient error"),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2)
        try:
            with patch.object(transport, "_backoff", new=AsyncMock()):
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            assert route.call_count == 2
        finally:
            await transport.close()

    @respx.mock
    async def test_timeout_retried_on_get(self) -> None:
        """TimeoutException on GET should be retried."""
        route = respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2)
        try:
            with patch.object(transport, "_backoff", new=AsyncMock()):
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            assert route.call_count == 2
        finally:
            await transport.close()

    def test_backoff_seconds_is_positive(self) -> None:
        """_backoff_seconds returns a positive value for all attempts."""
        from tradestation.transport import Transport as T

        for attempt in range(5):
            val = T._backoff_seconds(attempt)
            assert val > 0

    def test_backoff_seconds_capped(self) -> None:
        """_backoff_seconds should not exceed _BACKOFF_MAX."""
        from tradestation.transport import _BACKOFF_MAX
        from tradestation.transport import Transport as T

        for attempt in range(20):
            val = T._backoff_seconds(attempt)
            assert val <= _BACKOFF_MAX * 2  # allow jitter

    @respx.mock
    async def test_backoff_sleep_is_called(self) -> None:
        """_backoff() should call asyncio.sleep with a positive duration."""
        respx.get(f"{_BASE_URL}/marketdata/quotes/AAPL").mock(
            side_effect=[
                httpx.Response(503, json={}),
                httpx.Response(200, json={"Quotes": []}),
            ]
        )
        auth_mgr = _make_auth_manager()
        transport = Transport(_make_creds(), auth_manager=auth_mgr, retries=2)
        try:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await transport.request("GET", "/marketdata/quotes/AAPL")
            assert result == {"Quotes": []}
            assert mock_sleep.called
        finally:
            await transport.close()

    @respx.mock
    async def test_stream_unexpected_exception_raises_stream_error(self) -> None:
        """An unexpected exception in stream should be wrapped in StreamError."""
        auth_mgr = _make_auth_manager()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        class _FakeStreamCtx:
            async def __aenter__(self) -> None:
                raise RuntimeError("unexpected internal error")

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_client.stream.return_value = _FakeStreamCtx()

        transport = Transport(
            _make_creds(),
            auth_manager=auth_mgr,
            http_client=mock_client,
        )
        with pytest.raises(StreamError):
            stream_iter = await transport.stream("/marketdata/stream/quotes/AAPL")
            async for _ in stream_iter:
                pass
