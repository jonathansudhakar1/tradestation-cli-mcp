"""Safety guards for destructive MCP tools.

See docs/06-mcp-server.md §"Safety model for destructive tools".

Modes (--confirm-trades):
    off     — execute immediately (not recommended)
    require — require a confirmation token (default)
    review  — preview only; placement requires out-of-band CLI step
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token store (in-memory; single-process)
# ---------------------------------------------------------------------------

#: token_id -> (payload_hash, expires_at_epoch)
_TOKEN_STORE: dict[str, tuple[str, float]] = {}

TOKEN_TTL_SECONDS: float = 60.0


def generate_token(payload_hash: str) -> str:
    """Generate a single-use confirmation token bound to *payload_hash*.

    Tokens expire after :data:`TOKEN_TTL_SECONDS` (60 s).

    Args:
        payload_hash: A SHA-256 hex digest of the order payload being confirmed.

    Returns:
        A UUID4-style token string.
    """
    token = str(uuid.uuid4())
    expires_at = time.monotonic() + TOKEN_TTL_SECONDS
    _TOKEN_STORE[token] = (payload_hash, expires_at)
    return token


def verify_token(token: str, payload_hash: str) -> bool:
    """Verify and consume a confirmation token.

    Checks:
    - Token exists in the store.
    - Token has not expired.
    - Token is bound to *payload_hash*.
    - Deletes the token on success (single-use).

    Args:
        token: Token string returned by :func:`generate_token`.
        payload_hash: The SHA-256 hex digest that the token was issued for.

    Returns:
        ``True`` if the token is valid, ``False`` otherwise.
    """
    entry = _TOKEN_STORE.get(token)
    if entry is None:
        return False

    stored_hash, expires_at = entry

    if time.monotonic() > expires_at:
        del _TOKEN_STORE[token]
        return False

    if stored_hash != payload_hash:
        del _TOKEN_STORE[token]
        return False

    del _TOKEN_STORE[token]
    return True


def hash_payload(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest of a JSON-serialisable payload.

    Args:
        payload: The order payload dict to hash.

    Returns:
        Lowercase hex SHA-256 digest.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Notional cap check
# ---------------------------------------------------------------------------


def assert_notional_within_cap(preview: dict[str, Any], cap: float) -> None:
    """Raise :class:`ValueError` if the order preview exceeds *cap*.

    Looks for a ``EstimatedCost`` or ``estimatedCost`` field in *preview*.
    If neither is present, the check is skipped (conservative — do not block
    orders where we cannot determine cost).

    Args:
        preview: The order confirmation/preview dict from TradeStation.
        cap: Maximum allowed notional value in USD.

    Raises:
        ValueError: If the estimated cost exceeds the cap.
    """
    cost: float | None = None

    for key in ("EstimatedCost", "estimatedCost", "estimated_cost"):
        raw = preview.get(key)
        if raw is not None:
            with contextlib.suppress(TypeError, ValueError):
                cost = float(raw)
            break

    if cost is None:
        return

    if abs(cost) > cap:
        raise ValueError(
            f"Order notional {abs(cost):.2f} exceeds configured cap {cap:.2f}. "
            "Use --max-order-notional to raise the limit."
        )


# ---------------------------------------------------------------------------
# Symbol allowlist check
# ---------------------------------------------------------------------------


def assert_symbol_allowed(symbol: str, allowed_symbols: list[str]) -> None:
    """Raise :class:`ValueError` if *symbol* is not in *allowed_symbols*.

    If *allowed_symbols* is empty, all symbols are allowed.

    Args:
        symbol: The trading symbol to check (e.g. ``"AAPL"``).
        allowed_symbols: Allowlist; empty list means unrestricted.

    Raises:
        ValueError: If *symbol* is not in the allowlist.
    """
    if not allowed_symbols:
        return

    upper_symbol = symbol.upper()
    upper_allowed = [s.upper() for s in allowed_symbols]
    if upper_symbol not in upper_allowed:
        raise ValueError(
            f"Symbol '{symbol}' is not in the allowed-symbols list: "
            f"{', '.join(allowed_symbols)}. "
            "Use --allowed-symbols to add it."
        )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def _audit_log_path() -> Path:
    """Return the path to the MCP audit log."""
    tscli_dir = Path.home() / ".tscli"
    tscli_dir.mkdir(mode=0o700, exist_ok=True)
    return tscli_dir / "mcp-audit.log"


def write_audit_log(
    *,
    tool: str,
    account: str | None = None,
    payload: dict[str, Any] | None = None,
    preview_hash: str | None = None,
    decision: str,
    result: str,
) -> None:
    """Append a JSON audit log line to ``~/.tscli/mcp-audit.log``.

    Args:
        tool: The MCP tool name that was invoked.
        account: Trading account ID, if applicable.
        payload: The order payload sent (may be ``None``).
        preview_hash: The SHA-256 hash of the preview, if applicable.
        decision: One of ``"preview"``, ``"confirm"``, ``"reject"``, ``"skip"``
            (used when ``--confirm-trades off``).
        result: ``"success"`` or an error message.
    """
    log_path = _audit_log_path()
    entry: dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "tool": tool,
        "account": account,
        "payload": payload,
        "preview_hash": preview_hash,
        "decision": decision,
        "result": result,
        "pid": os.getpid(),
    }
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        logger.warning("Failed to write audit log to %s", log_path)
