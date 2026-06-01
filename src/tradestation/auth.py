"""AuthManager — refresh-token exchange and access-token lifecycle.

See docs/02-auth-and-credentials.md for the full design:
- Token endpoint: ``POST https://signin.tradestation.com/oauth/token``
- Proactive refresh via ``ensure_fresh()``
- Background ticker for long-running processes
- Rotation-aware atomic credential rewrite
- Redacting log filter (no secrets at any log level)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from tradestation.credentials import Credentials, save
from tradestation.errors import AuthError, NetworkError, RefreshTokenExpired, TimeoutError

_logger = logging.getLogger("tradestation")

_TOKEN_URL = "https://signin.tradestation.com/oauth/token"
_DEFAULT_SKEW_SECONDS = 60
_BACKGROUND_LEAD_SECONDS = 90  # Refresh this many seconds before expiry in background task


class AuthManager:
    """Manages access-token lifecycle for a single set of credentials.

    Callers obtain a fresh access token via :meth:`ensure_fresh`. The manager
    maintains an in-memory cache and proactively refreshes before expiry (60 s
    skew by default).

    Args:
        credentials: Frozen credential snapshot.
        skew_seconds: How many seconds before expiry to treat the token as
            stale and trigger a proactive refresh. Default: 60.
        creds_path: Path to the credentials file for rotation-aware saves.
            If None, uses the default path.
        http_client: Optional pre-built httpx.AsyncClient for testing.
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        skew_seconds: int = _DEFAULT_SKEW_SECONDS,
        creds_path: Path | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._credentials = credentials
        self._skew_seconds = skew_seconds
        self._creds_path = creds_path
        self._http_client = http_client

        # In-memory token cache
        self._access_token: str | None = credentials.access_token
        self._expires_at: float | None = _parse_expires_at(credentials.access_token_expires_at)

        # Background refresh task
        self._bg_task: asyncio.Task[None] | None = None
        self._expires_in: float = 1200.0  # default 20 min per TS docs

        # Lock for concurrent refresh calls
        self._refresh_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure_fresh(self) -> str:
        """Return a valid access token, refreshing if necessary.

        If the cached token expires within ``skew_seconds``, a refresh is
        performed first. Thread-safe: concurrent callers share one refresh.

        Raises:
            tradestation.errors.RefreshTokenExpired: If the refresh exchange
                returns 401 / ``invalid_grant``.
            tradestation.errors.NetworkError: On transport-level failure.
            tradestation.errors.TimeoutError: On request timeout.

        See docs/02-auth-and-credentials.md §"When we refresh".
        """
        if self._token_is_fresh():
            assert self._access_token is not None
            return self._access_token

        async with self._refresh_lock:
            # Re-check inside lock to avoid double refresh
            if self._token_is_fresh():
                assert self._access_token is not None
                return self._access_token

            await self._do_refresh()

        if self._access_token is None:
            raise AuthError("Token refresh succeeded but no access token was returned")
        return self._access_token

    async def refresh_now(self) -> Credentials:
        """Force an immediate token refresh and return updated credentials.

        Raises:
            tradestation.errors.RefreshTokenExpired: On ``invalid_grant``.

        See docs/02-auth-and-credentials.md §"Refresh exchange".
        """
        async with self._refresh_lock:
            await self._do_refresh()
        return self._credentials

    def start_background_refresh(self) -> None:
        """Start a background asyncio task that refreshes ahead of expiry.

        Safe to call multiple times — subsequent calls are no-ops if the task
        is already running.

        See docs/02-auth-and-credentials.md §"When we refresh" (point 2).
        """
        if self._bg_task is not None and not self._bg_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _logger.debug("No running event loop; background refresh not started")
            return
        self._bg_task = loop.create_task(
            self._background_refresh_loop(), name="tradestation-auth-refresh"
        )
        _logger.debug("Background refresh task started")

    def stop_background_refresh(self) -> None:
        """Cancel the background refresh task if running."""
        if self._bg_task is not None and not self._bg_task.done():
            self._bg_task.cancel()
            _logger.debug("Background refresh task cancelled")
        self._bg_task = None

    @property
    def credentials(self) -> Credentials:
        """Return the current (possibly updated) credentials snapshot."""
        return self._credentials

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _token_is_fresh(self) -> bool:
        """Return True iff the cached token is present and not about to expire."""
        if self._access_token is None:
            return False
        if self._expires_at is None:
            return False
        return (self._expires_at - time.monotonic()) > self._skew_seconds

    async def _do_refresh(self) -> None:
        """Perform the token refresh HTTP call and update cached state."""
        creds = self._credentials
        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "client_id": creds.client_id,
            "refresh_token": creds.refresh_token,
        }
        if creds.client_secret:
            data["client_secret"] = creds.client_secret

        _logger.info("Refreshing access token from %s", _TOKEN_URL)

        response_data = await self._post_token(data)

        access_token = response_data.get("access_token", "")
        if not access_token:
            raise AuthError("Token endpoint returned no access_token")

        expires_in = float(response_data.get("expires_in", 1200))
        id_token = response_data.get("id_token")
        new_refresh_token = response_data.get("refresh_token")

        # Update monotonic expiry clock
        self._expires_in = expires_in
        expires_monotonic = time.monotonic() + expires_in
        self._expires_at = expires_monotonic
        self._access_token = access_token

        # Build ISO-8601 wall-clock expiry for persistence
        expires_wall = datetime.now(timezone.utc).timestamp() + expires_in
        expires_at_iso = (
            datetime.fromtimestamp(expires_wall, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        # Build updated credentials
        updated = creds.replace(
            access_token=access_token,
            access_token_expires_at=expires_at_iso,
            id_token=id_token if id_token is not None else creds.id_token,
            refresh_token=new_refresh_token if new_refresh_token else creds.refresh_token,
        )
        self._credentials = updated

        # Persist rotation atomically if refresh token rotated or access token changed
        if self._creds_path is not None:
            try:
                save(updated, self._creds_path)
                _logger.debug("Credentials rotated and saved to %s", self._creds_path)
            except Exception as exc:
                _logger.warning("Failed to persist rotated credentials: %s", exc)

        _logger.info(
            "Access token acquired; expires in %.0fs", expires_in
        )

    async def _post_token(self, data: dict[str, str]) -> dict[str, Any]:
        """POST to the token endpoint and return the decoded JSON body."""
        own_client = False
        client = self._http_client
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            own_client = True

        try:
            try:
                response = await client.post(
                    _TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.TimeoutException as exc:
                raise TimeoutError(
                    f"Timeout connecting to token endpoint: {exc}"
                ) from exc
            except httpx.ConnectError as exc:
                raise NetworkError(
                    f"Network error connecting to token endpoint: {exc}"
                ) from exc
            except httpx.RequestError as exc:
                raise NetworkError(
                    f"Request error connecting to token endpoint: {exc}"
                ) from exc

            if response.status_code == 401:
                raise RefreshTokenExpired(
                    "Refresh token rejected (invalid_grant). "
                    "Run `ts auth login` or supply a new refresh token via `ts auth set`.",
                    status=401,
                )

            if response.status_code != 200:
                try:
                    payload: dict[str, Any] = response.json()
                except Exception:
                    payload = {}
                raise AuthError(
                    f"Token endpoint returned HTTP {response.status_code}",
                    status=response.status_code,
                    payload=payload,
                )

            return response.json()  # type: ignore[no-any-return]
        finally:
            if own_client:
                await client.aclose()

    async def _background_refresh_loop(self) -> None:
        """Continuously refresh the token ahead of expiry."""
        while True:
            try:
                # Wait until (expires_in - BACKGROUND_LEAD_SECONDS) seconds
                wait_time = max(self._expires_in - _BACKGROUND_LEAD_SECONDS, 30.0)
                _logger.debug("Background refresh sleeping for %.0fs", wait_time)
                await asyncio.sleep(wait_time)

                async with self._refresh_lock:
                    await self._do_refresh()
            except asyncio.CancelledError:
                _logger.debug("Background refresh task shutting down")
                return
            except RefreshTokenExpired:
                _logger.error(
                    "Background refresh failed: refresh token expired. "
                    "Run `ts auth login` to re-authenticate."
                )
                return
            except Exception as exc:
                _logger.warning("Background refresh error (will retry): %s", exc)
                await asyncio.sleep(30.0)


# ---------------------------------------------------------------------------
# Helper: parse ISO-8601 expiry → monotonic deadline
# ---------------------------------------------------------------------------


def _parse_expires_at(expires_at_iso: str | None) -> float | None:
    """Convert an ISO-8601 UTC timestamp to a monotonic deadline.

    Returns None if the timestamp is None or cannot be parsed.
    """
    if expires_at_iso is None:
        return None
    try:
        dt = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        wall_seconds_until = (dt - datetime.now(timezone.utc)).total_seconds()
        return time.monotonic() + wall_seconds_until
    except (ValueError, AttributeError):
        return None
