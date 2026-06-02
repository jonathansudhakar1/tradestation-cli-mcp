"""Credentials dataclass and load/save helpers.

See docs/02-auth-and-credentials.md for the full design:
- Storage path: ``~/.tscli/credentials`` (or ``$TS_CREDENTIALS``)
- Encryption: Fernet-v1 (AES-128-CBC + HMAC-SHA256) via ``cryptography``
- Key source: OS keyring (preferred) or PBKDF2 passphrase fallback
- Plaintext fallback: ``scheme: "plaintext"`` (requires explicit opt-in)

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
        "scope": "openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access",
        "environment": "sim",
        "access_token": "<opaque or null>",
        "access_token_expires_at": "2026-06-01T15:30:00Z",
        "id_token": "<JWT or null>",
        "saved_at": "2026-06-01T15:10:02Z",
    }
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import keyring
from cryptography.fernet import Fernet, InvalidToken
from filelock import FileLock

from tradestation.enums import Environment
from tradestation.errors import AuthError, NoCredentialsError

_logger = logging.getLogger("tradestation")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KEYRING_SERVICE = "tscli"
_KEYRING_ACCOUNT = "credentials-key-v1"
_KDF_ITERATIONS = 600_000
_SALT_BYTES = 24
_DEFAULT_SCOPE = (
    "openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access"
)


# ---------------------------------------------------------------------------
# Credentials dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Credentials:
    """Immutable snapshot of TradeStation credentials.

    Loaded from ``~/.tscli/credentials`` by :func:`load`, or constructed
    directly for programmatic / CI use.

    Attributes:
        client_id: OAuth client identifier.
        client_secret: OAuth client secret (empty string for PKCE clients).
        refresh_token: Long-lived refresh token.
        scope: Space-separated OAuth scopes.
        environment: API environment (live or sim). Default: SIM.
        access_token: Cached access token (may be ``None`` until first refresh).
        access_token_expires_at: ISO-8601 UTC timestamp when ``access_token``
            expires (may be ``None``).
        id_token: OIDC id token (may be ``None``).
        saved_at: ISO-8601 UTC timestamp when credentials were last saved.
    """

    client_id: str
    client_secret: str = ""
    refresh_token: str = ""
    scope: str = _DEFAULT_SCOPE
    environment: Environment = Environment.SIM
    access_token: str | None = None
    access_token_expires_at: str | None = None
    id_token: str | None = None
    saved_at: str | None = None

    @property
    def base_url(self) -> str:
        """Return the v3 REST base URL for the configured environment."""
        if self.environment == Environment.SIM:
            return "https://sim-api.tradestation.com/v3"
        return "https://api.tradestation.com/v3"

    def replace(self, **kwargs: Any) -> Credentials:
        """Return a new Credentials with the given fields replaced."""
        import dataclasses

        return dataclasses.replace(self, **kwargs)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _default_credentials_path() -> Path:
    """Return the default path for the credentials file.

    Respects the ``TS_CREDENTIALS`` environment variable when set.
    """
    return Path(os.environ.get("TS_CREDENTIALS", str(Path.home() / ".tscli" / "credentials")))


# Public alias for consumers (CLI, MCP, downstream code).
default_credentials_path = _default_credentials_path


def _lock_path(creds_path: Path) -> Path:
    return creds_path.with_suffix(".lock")


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------


def _keyring_get_key() -> bytes | None:
    """Try to retrieve the Fernet key from the OS keyring.

    Returns raw bytes of the Fernet key, or None if not found / unavailable.
    """
    try:
        value = keyring.get_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT)
        if value is None:
            return None
        return base64.urlsafe_b64decode(value.encode())
    except Exception:
        return None


def _keyring_set_key(key: bytes) -> bool:
    """Store the Fernet key in the OS keyring.

    Returns True on success, False if keyring is unavailable.
    """
    try:
        keyring.set_password(
            _KEYRING_SERVICE,
            _KEYRING_ACCOUNT,
            base64.urlsafe_b64encode(key).decode(),
        )
        return True
    except Exception:
        return False


def _derive_key_pbkdf2(passphrase: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a passphrase using PBKDF2-HMAC-SHA256."""
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode(),
        salt,
        _KDF_ITERATIONS,
    )
    # Fernet requires a 32-byte URL-safe base64 key
    return base64.urlsafe_b64encode(raw)


def _encrypt_payload(payload: dict[str, Any], use_keyring: bool = True) -> dict[str, Any]:
    """Encrypt payload dict and return the on-disk envelope dict.

    Tries keyring first; falls back to env-var passphrase (TSCLI_PASSPHRASE).
    """
    plaintext = json.dumps(payload, separators=(",", ":")).encode()
    salt = os.urandom(_SALT_BYTES)
    key: bytes | None = None

    if use_keyring:
        key = _keyring_get_key()
        if key is None:
            # Generate a new key and store it
            generated = Fernet.generate_key()
            if _keyring_set_key(generated):
                _logger.debug("Generated new Fernet key stored in OS keyring")
                key = generated
            else:
                _logger.warning("Keyring unavailable; falling back to PBKDF2 passphrase derivation")
                use_keyring = False

    if not use_keyring:
        passphrase = os.environ.get("TSCLI_PASSPHRASE", "")
        if not passphrase:
            # In production this would prompt; here we raise clearly
            raise AuthError(
                "Keyring unavailable and TSCLI_PASSPHRASE not set. "
                "Set TSCLI_PASSPHRASE or install a keyring backend."
            )
        key = _derive_key_pbkdf2(passphrase, salt)

    if key is None:
        raise AuthError("Failed to obtain an encryption key")

    fernet = Fernet(key)
    ciphertext = fernet.encrypt(plaintext)

    envelope: dict[str, Any] = {
        "version": 1,
        "scheme": "fernet-v1",
        "kdf": {
            "name": "pbkdf2_hmac_sha256",
            "iterations": _KDF_ITERATIONS,
            "salt_b64": base64.b64encode(salt).decode(),
        },
        "ciphertext_b64": base64.b64encode(ciphertext).decode(),
        "key_source": "keyring" if use_keyring else "passphrase",
    }
    return envelope


def _decrypt_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Decrypt an on-disk envelope dict and return the payload dict."""
    scheme = envelope.get("scheme", "plaintext")

    if scheme == "plaintext":
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise AuthError("Corrupt credentials file: plaintext payload missing or invalid")
        return payload

    if scheme != "fernet-v1":
        raise AuthError(f"Unknown credentials scheme: {scheme!r}")

    ciphertext = base64.b64decode(envelope["ciphertext_b64"])
    key_source = envelope.get("key_source", "keyring")
    kdf = envelope.get("kdf", {})
    salt = base64.b64decode(kdf.get("salt_b64", ""))

    if key_source == "keyring":
        key = _keyring_get_key()
        if key is None:
            raise AuthError(
                "Credentials were encrypted with the OS keyring but no key was found. "
                "Run `ts auth set` to re-configure."
            )
    else:
        passphrase = os.environ.get("TSCLI_PASSPHRASE", "")
        if not passphrase:
            raise AuthError(
                "Credentials were encrypted with a passphrase. Set TSCLI_PASSPHRASE to decrypt."
            )
        key = _derive_key_pbkdf2(passphrase, salt)

    try:
        fernet = Fernet(key)
        plaintext = fernet.decrypt(ciphertext)
    except InvalidToken as exc:
        raise AuthError("Failed to decrypt credentials: wrong key or corrupt data") from exc

    return json.loads(plaintext)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    """Write *content* to *path* atomically (tempfile + fsync + rename)."""
    parent = path.parent
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=".tmp_creds_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fobj:
            fobj.write(content)
            fobj.flush()
            os.fsync(fobj.fileno())
        os.chmod(tmp_name, mode)
        os.rename(tmp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise

    # Ensure 0600 on the final file
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# Payload ↔ Credentials conversion
# ---------------------------------------------------------------------------


def _payload_to_credentials(payload: dict[str, Any]) -> Credentials:
    """Build a Credentials instance from the decrypted payload dict."""
    env_str = payload.get("environment", "sim")
    try:
        env = Environment(env_str)
    except ValueError:
        env = Environment.SIM

    return Credentials(
        client_id=payload.get("client_id", ""),
        client_secret=payload.get("client_secret", ""),
        refresh_token=payload.get("refresh_token", ""),
        scope=payload.get("scope", _DEFAULT_SCOPE),
        environment=env,
        access_token=payload.get("access_token"),
        access_token_expires_at=payload.get("access_token_expires_at"),
        id_token=payload.get("id_token"),
        saved_at=payload.get("saved_at"),
    )


def _credentials_to_payload(creds: Credentials) -> dict[str, Any]:
    """Convert a Credentials instance to the payload dict for encryption."""
    saved_at = creds.saved_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "scope": creds.scope,
        "environment": creds.environment.value,
        "access_token": creds.access_token,
        "access_token_expires_at": creds.access_token_expires_at,
        "id_token": creds.id_token,
        "saved_at": saved_at,
    }


# ---------------------------------------------------------------------------
# Public API: load / save / from_env
# ---------------------------------------------------------------------------


def load(path: Path | None = None, *, profile: str | None = None) -> Credentials:
    """Load and decrypt credentials from *path* (default: ``~/.tscli/credentials``).

    Args:
        path: Override the file path. If None, uses ``TS_CREDENTIALS`` env var
            or ``~/.tscli/credentials``.
        profile: Named profile under ``~/.tscli/profiles/<profile>/credentials``.
            Overrides *path* when given.

    Raises:
        tradestation.errors.NoCredentialsError: If the credentials file does
            not exist or cannot be read.
        tradestation.errors.AuthError: If the file is present but cannot be
            decrypted (wrong key, corrupt ciphertext, etc.).
    """
    if profile is not None:
        creds_path = Path.home() / ".tscli" / "profiles" / profile / "credentials"
    elif path is not None:
        creds_path = path
    else:
        creds_path = _default_credentials_path()

    if not creds_path.exists():
        raise NoCredentialsError(
            f"Credentials file not found at {creds_path}. "
            "Run `ts auth set` to configure credentials."
        )

    with FileLock(str(_lock_path(creds_path))):
        try:
            raw = creds_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise NoCredentialsError(
                f"Cannot read credentials file at {creds_path}: {exc}"
            ) from exc

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthError(f"Credentials file is not valid JSON: {exc}") from exc

    payload = _decrypt_envelope(envelope)
    return _payload_to_credentials(payload)


def save(
    creds: Credentials,
    path: Path | None = None,
    *,
    profile: str | None = None,
    encrypt: bool = True,
    use_keyring: bool = True,
) -> None:
    """Encrypt and write *creds* to *path* (default: ``~/.tscli/credentials``).

    Creates ``~/.tscli/`` with mode ``0700`` if absent.
    Writes the file atomically (tempfile + fsync + rename) with mode ``0600``.
    Acquires ``path + '.lock'`` before writing to prevent concurrent corruption.

    Args:
        creds: Credentials to persist.
        path: Override the file path.
        profile: Named profile; overrides *path* when given.
        encrypt: Whether to encrypt (default True). If False, writes plaintext
            JSON with ``scheme: "plaintext"``.
        use_keyring: Whether to prefer the OS keyring for key storage.

    Raises:
        OSError: If the file cannot be written.
        tradestation.errors.AuthError: If encryption fails.
    """
    if profile is not None:
        creds_path = Path.home() / ".tscli" / "profiles" / profile / "credentials"
    elif path is not None:
        creds_path = path
    else:
        creds_path = _default_credentials_path()

    payload = _credentials_to_payload(creds)

    if encrypt:
        envelope = _encrypt_payload(payload, use_keyring=use_keyring)
    else:
        envelope = {
            "version": 1,
            "scheme": "plaintext",
            "payload": payload,
        }

    content = json.dumps(envelope, indent=2)

    with FileLock(str(_lock_path(creds_path))):
        _atomic_write(creds_path, content, mode=0o600)

    _logger.debug("Credentials saved to %s", creds_path)


def from_env() -> Credentials:
    """Build a :class:`Credentials` from environment variables.

    Reads:
        ``TS_CLIENT_ID``, ``TS_CLIENT_SECRET`` (optional),
        ``TS_REFRESH_TOKEN``, ``TS_SCOPE`` (optional),
        ``TS_ENV`` (optional; default: ``sim``).

    Raises:
        tradestation.errors.NoCredentialsError: If any required variable is
            missing.
    """
    client_id = os.environ.get("TS_CLIENT_ID", "")
    if not client_id:
        raise NoCredentialsError(
            "TS_CLIENT_ID environment variable is not set. "
            "Set TS_CLIENT_ID, TS_CLIENT_SECRET, and TS_REFRESH_TOKEN, "
            "or run `ts auth set`."
        )

    refresh_token = os.environ.get("TS_REFRESH_TOKEN", "")
    if not refresh_token:
        raise NoCredentialsError("TS_REFRESH_TOKEN environment variable is not set.")

    client_secret = os.environ.get("TS_CLIENT_SECRET", "")
    scope = os.environ.get("TS_SCOPE", _DEFAULT_SCOPE)
    env_str = os.environ.get("TS_ENV", "sim").lower()

    try:
        environment = Environment(env_str)
    except ValueError:
        _logger.warning("Unknown TS_ENV=%r; defaulting to SIM", env_str)
        environment = Environment.SIM

    return Credentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        scope=scope,
        environment=environment,
    )


# ---------------------------------------------------------------------------
# Legacy aliases (keep backward-compat with stub callers)
# ---------------------------------------------------------------------------


def load_credentials(path: Path | None = None) -> Credentials:
    """Alias for :func:`load`."""
    return load(path)


def save_credentials(credentials: Credentials, path: Path | None = None) -> None:
    """Alias for :func:`save`."""
    save(credentials, path)


def load_from_env() -> Credentials:
    """Alias for :func:`from_env`."""
    return from_env()


# ---------------------------------------------------------------------------
# CredentialsStore (keep stub class for backward compat)
# ---------------------------------------------------------------------------


@dataclass
class CredentialsStore:
    """Mutable handle to the on-disk credentials file."""

    path: Path = field(
        default_factory=_default_credentials_path,
    )
