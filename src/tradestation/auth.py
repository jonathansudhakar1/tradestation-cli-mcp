"""AuthManager — refresh-token exchange and access-token lifecycle.

See docs/02-auth-and-credentials.md for the full design:
- Token endpoint: ``POST https://signin.tradestation.com/oauth/token``
- Proactive refresh via ``ensure_fresh()``
- Background ticker for long-running processes
- Rotation-aware atomic credential rewrite
- Redacting log filter (no secrets at any log level)

Implementation: Phase 2.
"""

from __future__ import annotations

from tradestation.credentials import Credentials


class AuthManager:
    """Manages access-token lifecycle for a single set of credentials.

    Callers obtain a fresh access token via :meth:`ensure_fresh`. The manager
    maintains an in-memory cache and proactively refreshes before expiry (60 s
    skew by default).

    Args:
        credentials: Frozen credential snapshot. The manager keeps an internal
            mutable copy so that rotation-aware refresh can update the cached
            access token and (when the server rotates it) the refresh token.
        skew_seconds: How many seconds before expiry to treat the token as
            stale and trigger a proactive refresh. Default: 60.
    """

    def __init__(self, credentials: Credentials, *, skew_seconds: int = 60) -> None:
        self._credentials = credentials
        self._skew_seconds = skew_seconds

    async def ensure_fresh(self) -> str:
        """Return a valid access token, refreshing if necessary.

        Raises:
            tradestation.errors.RefreshTokenExpired: If the refresh exchange
                returns 401 / ``invalid_grant``.
            tradestation.errors.NetworkError: On transport-level failure.

        See docs/02-auth-and-credentials.md §"When we refresh".
        """
        raise NotImplementedError("see docs/02-auth-and-credentials.md §'When we refresh'")

    async def refresh_now(self) -> Credentials:
        """Force an immediate token refresh and return updated credentials.

        Raises:
            tradestation.errors.RefreshTokenExpired: On ``invalid_grant``.

        See docs/02-auth-and-credentials.md §"Refresh exchange".
        """
        raise NotImplementedError("see docs/02-auth-and-credentials.md §'Refresh exchange'")

    def start_background_refresh(self) -> None:
        """Start a background asyncio task that refreshes ahead of expiry.

        Safe to call multiple times — subsequent calls are no-ops if the task
        is already running.

        See docs/02-auth-and-credentials.md §"When we refresh" (point 2).
        """
        raise NotImplementedError(
            "see docs/02-auth-and-credentials.md §'When we refresh' (background tick)"
        )

    def stop_background_refresh(self) -> None:
        """Cancel the background refresh task if running."""
        raise NotImplementedError("see docs/02-auth-and-credentials.md §'When we refresh'")
