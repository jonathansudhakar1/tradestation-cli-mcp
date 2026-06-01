"""Fetch the TradeStation v3 OpenAPI spec and save to vendor/swagger.v3.json.

The v3 spec endpoint requires a Bearer token (401 without one).  This script:

1. Loads credentials from .env (via python-dotenv) or environment variables.
2. POSTs to signin.tradestation.com/oauth/token to exchange the refresh token
   for a short-lived access token.
3. GETs https://api.tradestation.com/v3/swagger.json (or
   https://sim-api.tradestation.com/v3/swagger.json when --env sim).
4. Writes the response to vendor/swagger.v3.json.
5. Writes vendor/swagger.v3.commit.txt with metadata (sha256, fetched_at, env).

Usage::

    python scripts/fetch_v3_spec.py             # defaults to --env sim
    python scripts/fetch_v3_spec.py --env live  # hits live API
    python scripts/fetch_v3_spec.py --env sim   # explicit sim

Environment variables (loaded from .env if present):

    TS_CLIENT_ID       — TradeStation OAuth client ID (required)
    TS_CLIENT_SECRET   — TradeStation OAuth client secret (required)
    TS_REFRESH_TOKEN   — Long-lived refresh token (required)
    TS_ENV             — "live" or "sim" (overridden by --env flag)

See docs/09-codegen-strategy.md §"The spec situation" for background.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# python-dotenv is a dev dependency — load .env when present
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore[import-untyped]

    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False


def _load_env(root: Path) -> None:
    """Load .env from the repository root if python-dotenv is available."""
    env_file = root / ".env"
    if _HAS_DOTENV and env_file.exists():
        _load_dotenv(env_file)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

_AUTH_URL = "https://signin.tradestation.com/oauth/token"
_LIVE_BASE = "https://api.tradestation.com/v3"
_SIM_BASE = "https://sim-api.tradestation.com/v3"


def _base_url(env: str) -> str:
    return _SIM_BASE if env == "sim" else _LIVE_BASE


def _exchange_refresh_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> str:
    """POST to the token endpoint and return the access token string."""
    payload = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        _AUTH_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(
            f"ERROR: Token exchange failed (HTTP {exc.code}): {raw}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"ERROR: Token exchange network error: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    access_token = body.get("access_token")
    if not access_token:
        print(
            f"ERROR: No access_token in response: {body}",
            file=sys.stderr,
        )
        sys.exit(1)
    return str(access_token)


# ---------------------------------------------------------------------------
# Spec fetch
# ---------------------------------------------------------------------------


def _fetch_spec(base_url: str, access_token: str) -> bytes:
    """GET /v3/swagger.json and return the raw bytes."""
    spec_url = f"{base_url}/swagger.json"
    req = urllib.request.Request(
        spec_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    print(f"Fetching: {spec_url} ...")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(
            f"ERROR: Spec fetch failed (HTTP {exc.code}): {raw}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"ERROR: Spec fetch network error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_commit_txt(out_file: Path, env: str, sha256: str, spec_url: str) -> None:
    fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = (
        f"source:      {spec_url}\n"
        f"env:         {env}\n"
        f"fetched_at:  {fetched_at}\n"
        f"sha256:      {sha256}\n"
        f"spec_version: openapi 3.x (v3)\n"
    )
    out_file.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch the TradeStation v3 OpenAPI spec and vendor it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--env",
        choices=["sim", "live"],
        default=None,
        help=("API environment to fetch the spec from. Default: 'sim' (or TS_ENV env var if set)."),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point — fetch v3 spec and write to vendor/."""
    root = Path(__file__).resolve().parent.parent
    _load_env(root)

    args = _parse_args(argv)

    # Resolve env: CLI flag > TS_ENV > default "sim"
    env_from_var = os.environ.get("TS_ENV", "").strip().lower()
    if args.env is not None:
        env = args.env
    elif env_from_var in ("live", "sim"):
        env = env_from_var
    else:
        env = "sim"

    # Load credentials
    client_id = os.environ.get("TS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("TS_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("TS_REFRESH_TOKEN", "").strip()

    missing = [
        name
        for name, val in [
            ("TS_CLIENT_ID", client_id),
            ("TS_CLIENT_SECRET", client_secret),
            ("TS_REFRESH_TOKEN", refresh_token),
        ]
        if not val
    ]
    if missing:
        print(
            f"ERROR: Missing required env vars: {', '.join(missing)}\n"
            "       Set them in .env or export them before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Environment: {env}")
    print("Exchanging refresh token for access token ...")
    access_token = _exchange_refresh_token(client_id, client_secret, refresh_token)
    print("Token obtained.")

    base_url = _base_url(env)
    spec_bytes = _fetch_spec(base_url, access_token)
    print(f"Fetched {len(spec_bytes)} bytes.")

    # Validate it's JSON
    try:
        json.loads(spec_bytes)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Response is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    sha256 = _compute_sha256(spec_bytes)
    vendor_dir = root / "vendor"
    vendor_dir.mkdir(exist_ok=True)

    out_json = vendor_dir / "swagger.v3.json"
    out_json.write_bytes(spec_bytes)
    print(f"Wrote {out_json} ({len(spec_bytes)} bytes, sha256={sha256[:12]}...)")

    out_commit = vendor_dir / "swagger.v3.commit.txt"
    _write_commit_txt(out_commit, env, sha256, f"{base_url}/swagger.json")
    print(f"Wrote {out_commit}")

    print("\nDone. Commit vendor/swagger.v3.json + vendor/swagger.v3.commit.txt in your PR.")


if __name__ == "__main__":
    main()
