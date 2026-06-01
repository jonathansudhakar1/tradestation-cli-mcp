"""Unit tests for tradestation.auth.

Tests:
    - respx-mocked refresh exchange
    - expiry math with freezegun
    - ensure_fresh skew (does not refresh when fresh)
    - ensure_fresh triggers refresh when stale
    - refresh-token rotation handling
    - error mapping: 401 → RefreshTokenExpired
    - error mapping: 5xx → AuthError
    - background refresh task start/stop
    - concurrent ensure_fresh calls share one refresh
"""

from __future__ import annotations

import asyncio
import contextlib
import pathlib
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from tradestation.auth import AuthManager, _parse_expires_at
from tradestation.credentials import Credentials
from tradestation.enums import Environment
from tradestation.errors import AuthError, NetworkError, RefreshTokenExpired, TimeoutError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creds(
    access_token: str | None = None,
    access_token_expires_at: str | None = None,
    refresh_token: str = "rt",
) -> Credentials:
    return Credentials(
        client_id="cid",
        client_secret="csec",
        refresh_token=refresh_token,
        environment=Environment.SIM,
        access_token=access_token,
        access_token_expires_at=access_token_expires_at,
    )


_TOKEN_URL = "https://signin.tradestation.com/oauth/token"


# ---------------------------------------------------------------------------
# _parse_expires_at helper
# ---------------------------------------------------------------------------


class TestParseExpiresAt:
    def test_none_returns_none(self) -> None:
        assert _parse_expires_at(None) is None

    def test_invalid_string_returns_none(self) -> None:
        assert _parse_expires_at("not-a-date") is None

    def test_future_date_positive_offset(self) -> None:
        # One hour from now
        future = "2099-01-01T00:00:00Z"
        deadline = _parse_expires_at(future)
        assert deadline is not None
        assert deadline > time.monotonic()

    def test_past_date_negative_offset(self) -> None:
        past = "2000-01-01T00:00:00Z"
        deadline = _parse_expires_at(past)
        assert deadline is not None
        assert deadline < time.monotonic()


# ---------------------------------------------------------------------------
# Token freshness check
# ---------------------------------------------------------------------------


class TestTokenFreshness:
    def test_no_token_not_fresh(self) -> None:
        mgr = AuthManager(_make_creds())
        assert not mgr._token_is_fresh()

    def test_fresh_token_stays_fresh(self) -> None:
        # Expires far in the future
        creds = _make_creds(
            access_token="valid-token",
            access_token_expires_at="2099-12-31T23:59:59Z",
        )
        mgr = AuthManager(creds, skew_seconds=60)
        assert mgr._token_is_fresh()

    def test_about_to_expire_not_fresh(self) -> None:
        # Expires in 30 seconds, skew is 60 → not fresh
        creds = _make_creds(
            access_token="stale-token",
            # we'll manually override _expires_at
        )
        mgr = AuthManager(creds, skew_seconds=60)
        mgr._access_token = "stale-token"
        mgr._expires_at = time.monotonic() + 30  # 30s remaining, skew=60
        assert not mgr._token_is_fresh()

    def test_zero_expires_at_not_fresh(self) -> None:
        creds = _make_creds(access_token="tok")
        mgr = AuthManager(creds)
        mgr._access_token = "tok"
        mgr._expires_at = None
        assert not mgr._token_is_fresh()


# ---------------------------------------------------------------------------
# Refresh exchange — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefreshExchange:
    @respx.mock
    async def test_successful_refresh(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        creds = _make_creds()
        mgr = AuthManager(creds)

        token = await mgr.ensure_fresh()
        assert token == "new-access-token-abc123"

    @respx.mock
    async def test_refresh_updates_credentials(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        creds = _make_creds()
        mgr = AuthManager(creds)

        await mgr.ensure_fresh()
        updated = mgr.credentials
        assert updated.access_token == "new-access-token-abc123"
        assert updated.id_token == "new-id-token-xyz"

    @respx.mock
    async def test_refresh_with_rotation(
        self,
        refresh_response_with_rotation: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, json=refresh_response_with_rotation)
        )
        creds = _make_creds(refresh_token="old-rt")
        mgr = AuthManager(creds)

        await mgr.ensure_fresh()
        assert mgr.credentials.refresh_token == "rotated-refresh-token-99999"

    @respx.mock
    async def test_no_double_refresh_when_fresh(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        creds = _make_creds(
            access_token="already-valid",
            access_token_expires_at="2099-12-31T23:59:59Z",
        )
        mgr = AuthManager(creds)

        token = await mgr.ensure_fresh()
        assert token == "already-valid"
        # Should NOT have called the token endpoint
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_concurrent_refresh_calls_one_http_request(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        creds = _make_creds()  # no token
        mgr = AuthManager(creds)

        # Fire 5 concurrent ensure_fresh calls
        tokens = await asyncio.gather(*[mgr.ensure_fresh() for _ in range(5)])
        assert all(t == "new-access-token-abc123" for t in tokens)
        # Only one actual HTTP request should have been made
        assert respx.calls.call_count == 1


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorMapping:
    @respx.mock
    async def test_401_raises_refresh_token_expired(self) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                401,
                json={"error": "invalid_grant", "error_description": "Refresh token expired"},
            )
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(RefreshTokenExpired):
            await mgr.ensure_fresh()

    @respx.mock
    async def test_500_raises_auth_error(self) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(500, json={"error": "server_error"})
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(AuthError):
            await mgr.ensure_fresh()

    @respx.mock
    async def test_timeout_raises_timeout_error(self) -> None:
        respx.post(_TOKEN_URL).mock(side_effect=httpx.TimeoutException("timed out"))
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(TimeoutError):
            await mgr.ensure_fresh()

    @respx.mock
    async def test_connect_error_raises_network_error(self) -> None:
        respx.post(_TOKEN_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(NetworkError):
            await mgr.ensure_fresh()

    @respx.mock
    async def test_refresh_token_expired_human_message(self) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(401, json={"error": "invalid_grant"})
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(RefreshTokenExpired) as exc_info:
            await mgr.ensure_fresh()

        assert "ts auth login" in exc_info.value.human_message()


# ---------------------------------------------------------------------------
# Expiry math with freezegun
# ---------------------------------------------------------------------------


class TestExpiryMath:
    @respx.mock
    async def test_expires_in_sets_cache(
        self,
    ) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "token_type": "Bearer",
                    "expires_in": 1200,
                    "scope": "openid",
                },
            )
        )
        creds = _make_creds()
        mgr = AuthManager(creds)
        before = time.monotonic()
        await mgr.ensure_fresh()
        after = time.monotonic()

        assert mgr._expires_at is not None
        # Should be ~1200s from now
        assert mgr._expires_at > before + 1190
        assert mgr._expires_at < after + 1210

    @respx.mock
    async def test_second_call_uses_cache(
        self,
    ) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "tok", "token_type": "Bearer", "expires_in": 1200},
            )
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        await mgr.ensure_fresh()
        assert respx.calls.call_count == 1

        await mgr.ensure_fresh()
        # Second call should NOT hit the network
        assert respx.calls.call_count == 1


# ---------------------------------------------------------------------------
# refresh_now
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefreshNow:
    @respx.mock
    async def test_refresh_now_returns_updated_credentials(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        creds = _make_creds()
        mgr = AuthManager(creds)
        updated = await mgr.refresh_now()
        assert updated.access_token == "new-access-token-abc123"


# ---------------------------------------------------------------------------
# Background refresh task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBackgroundRefresh:
    async def test_start_stop_background_task(self) -> None:
        creds = _make_creds(
            access_token="tok",
            access_token_expires_at="2099-12-31T23:59:59Z",
        )
        mgr = AuthManager(creds)

        mgr.start_background_refresh()
        assert mgr._bg_task is not None
        assert not mgr._bg_task.done()

        # Start again → no-op
        mgr.start_background_refresh()
        task1 = mgr._bg_task

        mgr.start_background_refresh()
        assert mgr._bg_task is task1  # same task

        mgr.stop_background_refresh()
        assert mgr._bg_task is None

    async def test_stop_without_start_is_noop(self) -> None:
        mgr = AuthManager(_make_creds())
        mgr.stop_background_refresh()  # should not raise


# ---------------------------------------------------------------------------
# Rotation-aware credential save
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRotationSave:
    @respx.mock
    async def test_rotated_token_persisted(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
        refresh_response_with_rotation: dict[str, object],
    ) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, json=refresh_response_with_rotation)
        )
        creds_path = tmp_credentials_dir / "credentials"
        creds = _make_creds(refresh_token="original-rt")

        # Save initial creds
        from tradestation.credentials import save as creds_save

        creds_save(creds, creds_path)

        mgr = AuthManager(creds, creds_path=creds_path)
        await mgr.ensure_fresh()

        # Load and check rotation was saved
        from tradestation.credentials import load as creds_load

        updated = creds_load(creds_path)
        assert updated.refresh_token == "rotated-refresh-token-99999"


# ---------------------------------------------------------------------------
# PKCE (no client_secret) path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPKCEPath:
    @respx.mock
    async def test_no_client_secret_omitted_from_request(
        self,
    ) -> None:
        """PKCE clients have no client_secret; it must not appear in the form body."""
        route = respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "tok", "token_type": "Bearer", "expires_in": 1200},
            )
        )
        creds = Credentials(
            client_id="pkce-client",
            client_secret="",  # PKCE: no secret
            refresh_token="rt",
            environment=Environment.SIM,
        )
        mgr = AuthManager(creds)
        await mgr.ensure_fresh()

        assert route.called
        body = route.calls.last.request.content.decode()
        assert "client_secret" not in body


# ---------------------------------------------------------------------------
# Empty access_token in response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEmptyAccessToken:
    @respx.mock
    async def test_empty_access_token_raises_auth_error(self) -> None:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "", "token_type": "Bearer", "expires_in": 1200},
            )
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(AuthError):
            await mgr.ensure_fresh()


# ---------------------------------------------------------------------------
# RequestError (generic) → NetworkError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRequestError:
    @respx.mock
    async def test_request_error_raises_network_error(self) -> None:
        respx.post(_TOKEN_URL).mock(side_effect=httpx.RequestError("generic request error"))
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(NetworkError):
            await mgr.ensure_fresh()


# ---------------------------------------------------------------------------
# Injected http_client is used (own_client=False path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInjectedHttpClient:
    @respx.mock
    async def test_injected_http_client_not_closed(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        """Injected http_client should NOT be closed after the request."""
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        # Use a real httpx client but wrap it
        import httpx as _httpx

        outer_client = _httpx.AsyncClient()
        try:
            creds = _make_creds()
            mgr = AuthManager(creds, http_client=outer_client)
            await mgr.ensure_fresh()
            assert mgr._access_token == "new-access-token-abc123"
        finally:
            await outer_client.aclose()


# ---------------------------------------------------------------------------
# Save failure during rotation → warning only, no exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSaveFailureDuringRotation:
    @respx.mock
    async def test_save_failure_does_not_propagate(
        self,
        refresh_response: dict[str, object],
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        """A failure to save credentials during rotation should log a warning, not raise."""
        respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json=refresh_response))
        import os

        creds = _make_creds()
        read_only_dir = tmp_credentials_dir / "readonly"
        read_only_dir.mkdir()
        os.chmod(read_only_dir, 0o444)
        ro_path = read_only_dir / "credentials"
        mgr = AuthManager(creds, creds_path=ro_path)
        # Should complete without raising
        try:
            token = await mgr.ensure_fresh()
            assert token == "new-access-token-abc123"
        finally:
            os.chmod(read_only_dir, 0o700)


# ---------------------------------------------------------------------------
# Double-lock check: second caller in lock reuses cached token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDoubleLockCheck:
    @respx.mock
    async def test_second_waiter_reuses_result(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        """After the lock is released, subsequent waiters should reuse the cached token."""
        call_count = 0
        original_response = dict(refresh_response)

        async def _side_effect(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return httpx.Response(200, json=original_response)

        respx.post(_TOKEN_URL).mock(side_effect=_side_effect)
        creds = _make_creds()
        mgr = AuthManager(creds)

        # Fire two concurrent requests that both see a stale token
        tokens = await asyncio.gather(mgr.ensure_fresh(), mgr.ensure_fresh())
        assert tokens[0] == tokens[1] == "new-access-token-abc123"
        # The side_effect should have been called exactly once
        assert call_count == 1


# ---------------------------------------------------------------------------
# Non-JSON error response from token endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNonJsonErrorResponse:
    @respx.mock
    async def test_non_json_error_response_still_raises(self) -> None:
        """A non-JSON error body from the token endpoint should not crash."""
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(503, content=b"Service Unavailable (plain text)")
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        with pytest.raises(AuthError) as exc_info:
            await mgr.ensure_fresh()
        assert exc_info.value.status == 503


# ---------------------------------------------------------------------------
# Background refresh loop actually executes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBackgroundRefreshLoop:
    @respx.mock
    async def test_background_loop_refreshes(
        self,
        refresh_response: dict[str, object],
    ) -> None:
        """Background loop should call the token endpoint when sleep expires."""
        refresh_done = asyncio.Event()
        call_count = 0
        real_sleep = asyncio.sleep

        async def _token_side_effect(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            refresh_done.set()
            return httpx.Response(200, json=refresh_response)

        async def _fast_sleep(duration: float) -> None:
            # return immediately so the loop runs right away
            await real_sleep(0)

        respx.post(_TOKEN_URL).mock(side_effect=_token_side_effect)

        creds = _make_creds()
        mgr = AuthManager(creds)

        with patch("tradestation.auth.asyncio.sleep", side_effect=_fast_sleep):
            mgr.start_background_refresh()
            assert mgr._bg_task is not None
            # Wait for refresh to happen (or give up after a few yields)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(refresh_done.wait(), timeout=1.0)
            mgr.stop_background_refresh()

        assert call_count >= 1

    @respx.mock
    async def test_background_loop_stops_on_expired_token(self) -> None:
        """Background loop should stop when RefreshTokenExpired is raised."""
        real_sleep = asyncio.sleep

        async def _fast_sleep(duration: float) -> None:
            await real_sleep(0)

        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(401, json={"error": "invalid_grant"})
        )
        creds = _make_creds()
        mgr = AuthManager(creds)

        with patch("tradestation.auth.asyncio.sleep", side_effect=_fast_sleep):
            mgr.start_background_refresh()
            task = mgr._bg_task
            assert task is not None
            # Wait for task to complete due to RefreshTokenExpired
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), timeout=1.0)

        mgr.stop_background_refresh()

    async def test_background_refresh_error_retries(self) -> None:
        """Background loop should not stop on non-auth errors (NetworkError)."""
        creds = _make_creds(
            access_token="valid",
            access_token_expires_at="2099-12-31T23:59:59Z",
        )
        mgr = AuthManager(creds)

        # We're just checking the loop starts and can be stopped
        mgr.start_background_refresh()
        assert mgr._bg_task is not None
        mgr.stop_background_refresh()
        assert mgr._bg_task is None
