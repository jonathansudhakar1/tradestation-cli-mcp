"""Credentials dataclass and load/save helpers.

See docs/02-auth-and-credentials.md for the full design:
- Storage path: ``~/.tscli/credentials`` (or ``$TS_CREDENTIALS``)
- Encryption: Fernet-v1 (AES-128-CBC + HMAC-SHA256) via ``cryptography``
- Key source: OS keyring (preferred) or PBKDF2 passphrase fallback
- Plaintext fallback: ``scheme: "plaintext"`` (requires ``--no-encrypt``)

On-disk JSON envelope (scheme="fernet-v1")::

    {
        "version": 1,
        "scheme": "fernet-v1",
        "kdf": {
            "name": "pbkdf2_hmac_sha256",
            "iterations": 600000,
            "salt_b64": "<24 random bytes, base64>",
        },
        "ciphertext_b64": "<Fernet token>",
    }

Decrypted payload::

    {
        "client_id": "<opaque>",
        "client_secret": "<opaque>",
        "refresh_token": "<opaque>",
        "scope": "openid offline_access MarketData ReadAccount Trade",
        "environment": "live",
        "access_token": "<opaque or null>",
        "access_token_expires_at": "2026-06-01T15:30:00Z",
        "id_token": "<JWT or null>",
        "saved_at": "2026-06-01T15:10:02Z",
    }

Implementation: Phase 2 (docs/02-auth-and-credentials.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from tradestation.enums import Environment


@dataclass(frozen=True)
class Credentials:
    """Immutable snapshot of TradeStation credentials.

    Loaded from ``~/.tscli/credentials`` by :func:`load_credentials`, or
    constructed directly for programmatic / CI use.

    Attributes:
        client_id: OAuth client identifier.
        client_secret: OAuth client secret (empty string for PKCE clients).
        refresh_token: Long-lived refresh token.
        scope: Space-separated OAuth scopes.
        environment: API environment (live or sim).
        access_token: Cached access token (may be ``None`` until first refresh).
        access_token_expires_at: ISO-8601 UTC timestamp when ``access_token``
            expires (may be ``None``).
        id_token: OIDC id token (may be ``None``).
    """

    client_id: str
    client_secret: str
    refresh_token: str
    scope: str = "openid offline_access MarketData ReadAccount Trade"
    environment: Environment = Environment.LIVE
    access_token: str | None = None
    access_token_expires_at: str | None = None
    id_token: str | None = None

    @property
    def base_url(self) -> str:
        """Return the v3 REST base URL for the configured environment."""
        if self.environment == Environment.SIM:
            return "https://sim-api.tradestation.com/v3"
        return "https://api.tradestation.com/v3"


@dataclass
class CredentialsStore:
    """Mutable handle to the on-disk credentials file.

    Use :func:`load_credentials` to obtain a :class:`Credentials` snapshot.
    Use :meth:`save` to persist updated credentials (e.g. after token refresh).
    """

    path: Path = field(
        default_factory=lambda: default_credentials_path(),
    )


def default_credentials_path() -> Path:
    """Return the default path for the credentials file.

    Respects the ``TS_CREDENTIALS`` environment variable when set.
    """
    return Path(os.environ.get("TS_CREDENTIALS", str(Path.home() / ".tscli" / "credentials")))


def load_credentials(path: Path | None = None) -> Credentials:
    """Load and decrypt credentials from *path* (default: ``~/.tscli/credentials``).

    Raises:
        tradestation.errors.NoCredentialsError: If the credentials file does
            not exist or cannot be read.
        tradestation.errors.AuthError: If the file is present but cannot be
            decrypted (wrong passphrase, corrupt ciphertext, etc.).

    See docs/02-auth-and-credentials.md §"Encryption-at-rest scheme".
    """
    raise NotImplementedError("see docs/02-auth-and-credentials.md §'Encryption-at-rest scheme'")


def save_credentials(credentials: Credentials, path: Path | None = None) -> None:
    """Encrypt and write *credentials* to *path* (default: ``~/.tscli/credentials``).

    Creates ``~/.tscli/`` with mode ``0700`` if absent.
    Writes the file atomically (tempfile + rename) with mode ``0600``.
    Acquires ``path + '.lock'`` before writing to prevent concurrent corruption.

    Raises:
        OSError: If the file cannot be written.

    See docs/02-auth-and-credentials.md §"Encryption-at-rest scheme".
    """
    raise NotImplementedError("see docs/02-auth-and-credentials.md §'Encryption-at-rest scheme'")


def load_from_env() -> Credentials:
    """Build a :class:`Credentials` from environment variables.

    Reads:
        ``TS_CLIENT_ID``, ``TS_CLIENT_SECRET``, ``TS_REFRESH_TOKEN``,
        ``TS_SCOPE`` (optional), ``TS_ENV`` (optional; default: ``live``).

    Raises:
        tradestation.errors.NoCredentialsError: If any required variable is
            missing.
    """
    raise NotImplementedError("see docs/02-auth-and-credentials.md §'Library API'")
