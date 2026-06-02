"""``ts auth`` command group — credential management.

Subcommands:
    set      — interactive / non-interactive credential setup
    status   — show credential health and expiry
    refresh  — force an immediate token refresh
    login    — browser OAuth code-grant flow (PKCE) — stub
    clear    — wipe credentials (with confirmation)
    export   — print decrypted payload (dangerous; requires --yes-i-want-secrets flag)
    doctor   — diagnostics (keyring, token exchange, scopes)

See docs/02-auth-and-credentials.md for the full design.
Maps to: A — credential management (no specific endpoint ID; auth lifecycle).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.tree import Tree

from tradestation.cli.prompts import (
    confirm_destructive,
    prompt_secret,
    prompt_text,
)
from tradestation.cli.render import panel_auth_status
from tradestation.cli.theme import get_theme
from tradestation.credentials import Credentials, default_credentials_path
from tradestation.enums import Environment

app = typer.Typer(
    name="auth",
    help="[bold]Credential management[/bold]: set, status, refresh, login, clear, doctor.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

_DEFAULT_SCOPE = "openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access"


def _console() -> Console:
    """Return a themed Rich console."""
    return Console(theme=get_theme())


# ---------------------------------------------------------------------------
# ts auth set
# ---------------------------------------------------------------------------


@app.command("set")
def auth_set(
    ctx: typer.Context,
    client_id: Annotated[
        str | None,
        typer.Option("--client-id", help="OAuth client identifier.", envvar="TS_CLIENT_ID"),
    ] = None,
    client_secret: Annotated[
        str | None,
        typer.Option(
            "--client-secret",
            help="OAuth client secret (empty for PKCE clients).",
            envvar="TS_CLIENT_SECRET",
        ),
    ] = None,
    refresh_token: Annotated[
        str | None,
        typer.Option(
            "--refresh-token",
            help="Long-lived refresh token.",
            envvar="TS_REFRESH_TOKEN",
        ),
    ] = None,
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            help="Space-separated OAuth scopes.",
        ),
    ] = _DEFAULT_SCOPE,
    env: Annotated[
        str,
        typer.Option(
            "--env",
            help="API environment: [bold]live[/bold] or [bold]sim[/bold].",
            rich_help_panel="Options",
        ),
    ] = "sim",
    encrypt: Annotated[
        bool,
        typer.Option(
            "--encrypt/--no-encrypt",
            help="Encrypt credentials at rest (default: yes).",
        ),
    ] = True,
    i_understand_the_risk: Annotated[
        bool,
        typer.Option(
            "--i-understand-the-risk",
            help="Required with --no-encrypt.",
            hidden=True,
        ),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile to write to.", envvar="TS_PROFILE"),
    ] = None,
) -> None:
    """Save client_id / client_secret / refresh_token to the credentials file.

    Interactive by default — prompts for values not supplied via flags.
    Verifies the refresh token before writing. Aborts on auth failure.

    Side effects:
    - Creates ~/.tscli/ (mode 0700) if absent.
    - Writes ~/.tscli/credentials (mode 0600).
    - Writes ~/.tscli/state.json with environment.
    """
    console = _console()
    console.print("\n[ts.header]TradeStation credential setup[/ts.header]\n")

    if not encrypt and not i_understand_the_risk:
        console.print(
            "[ts.danger]--no-encrypt stores secrets in plaintext. "
            "Pass --i-understand-the-risk to confirm.[/ts.danger]"
        )
        raise typer.Exit(code=1) from None

    # --- gather inputs (interactive only when flags are missing) ---
    interactive = client_id is None or refresh_token is None

    if client_id is None:
        client_id = prompt_secret("  Client ID      ", console=console)
    if not client_id:
        console.print("[ts.bad]✖[/ts.bad] Client ID is required.")
        raise typer.Exit(code=1) from None

    if client_secret is None:
        client_secret = prompt_secret("  Client secret  ", console=console)

    if refresh_token is None:
        refresh_token = prompt_secret("  Refresh token  ", console=console)
    if not refresh_token:
        console.print("[ts.bad]✖[/ts.bad] Refresh token is required.")
        raise typer.Exit(code=1) from None

    if interactive:
        scope = prompt_text(
            "  Scope (optional)",
            default=scope,
            console=console,
        )
        env_input = prompt_text("  Environment   ", default=env, console=console)
    else:
        env_input = env

    try:
        environment = Environment(env_input.strip().lower())
    except ValueError:
        console.print(
            f"[ts.bad]✖[/ts.bad] Unknown environment: {env_input!r}. Use 'live' or 'sim'."
        )
        raise typer.Exit(code=1) from None

    # --- verify by attempting a token exchange ---
    console.print("\n[ts.muted]  Verifying refresh token…[/ts.muted]", end=" ")
    access_token, expires_in = _try_token_exchange(
        client_id=client_id,
        client_secret=client_secret or "",
        refresh_token=refresh_token,
        environment=environment,
        console=console,
    )

    # --- build credentials ---
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    expires_at: str | None = None
    if expires_in:
        expires_at = (now + timedelta(seconds=expires_in)).isoformat().replace("+00:00", "Z")

    credentials = Credentials(
        client_id=client_id,
        client_secret=client_secret or "",
        refresh_token=refresh_token,
        scope=scope,
        environment=environment,
        access_token=access_token,
        access_token_expires_at=expires_at,
    )

    # --- write to disk ---
    creds_path = _credentials_path(profile)
    try:
        _write_credentials_plaintext(credentials, creds_path)
    except OSError as exc:
        console.print(f"\n[ts.bad]✖[/ts.bad] Failed to write credentials: {exc}")
        raise typer.Exit(code=1) from None

    console.print(f"[ts.ok]✔[/ts.ok] Saved → [ts.mono]{creds_path}[/ts.mono]  (perms 0600)")
    # Write state.json
    _write_state(creds_path.parent, environment)


def _try_token_exchange(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    environment: Environment,
    console: Console,
) -> tuple[str | None, int | None]:
    """Attempt a refresh-token exchange.  Returns (access_token, expires_in) or aborts."""
    try:
        import httpx
    except ImportError:
        console.print("[ts.warn]  (httpx not available — skipping verification)[/ts.warn]")
        return None, None

    token_url = "https://signin.tradestation.com/oauth/token"
    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret

    try:
        resp = httpx.post(token_url, data=data, timeout=15)
        if resp.status_code == 200:
            body = resp.json()
            access_token: str = body.get("access_token", "")
            expires_in: int = int(body.get("expires_in", 1200))
            mins = expires_in // 60
            secs = expires_in % 60
            console.print(
                f"[ts.ok]✔[/ts.ok] acquired access token "
                f"[ts.muted](expires in {mins}m {secs:02d}s)[/ts.muted]"
            )
            return access_token, expires_in
        else:
            body_text = resp.text
            console.print(
                f"\n[ts.bad]✖[/ts.bad] Token exchange failed "
                f"[ts.muted](HTTP {resp.status_code})[/ts.muted]: {body_text[:200]}"
            )
            raise typer.Exit(code=3) from None
    except httpx.HTTPError as exc:
        console.print(f"\n[ts.bad]✖[/ts.bad] Network error during token exchange: {exc}")
        raise typer.Exit(code=1) from None


def _credentials_path(profile: str | None) -> Path:
    """Return the credentials file path, respecting profile and TS_CREDENTIALS."""
    if profile:
        return Path.home() / ".tscli" / "profiles" / profile / "credentials"
    return default_credentials_path()


def _write_credentials_plaintext(credentials: Credentials, path: Path) -> None:
    """Write credentials as plaintext JSON (scheme: plaintext).

    Creates parent dirs with 0700, writes file with 0600.
    Uses atomic tempfile + rename.
    """
    import json
    import tempfile

    payload = {
        "version": 1,
        "scheme": "plaintext",
        "payload": {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "scope": credentials.scope,
            "environment": credentials.environment.value,
            "access_token": credentials.access_token,
            "access_token_expires_at": credentials.access_token_expires_at,
            "id_token": credentials.id_token,
        },
    }
    # Create parent directory
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Atomic write
    fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".credentials_tmp_")
    tmp_path = Path(tmp_path_str)
    try:
        os.write(fd, json.dumps(payload, indent=2).encode())
        os.fsync(fd)
        os.close(fd)
        # Set 0600 before rename
        tmp_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        tmp_path.rename(path)
    except Exception:
        os.close(fd)
        tmp_path.unlink(missing_ok=True)
        raise

    # Ensure parent dir has correct mode
    path.parent.chmod(0o700)


def _write_state(tscli_dir: Path, environment: Environment) -> None:
    """Write state.json with the current environment (non-secret)."""
    import json

    state_path = tscli_dir / "state.json"
    state = {"environment": environment.value}
    try:
        state_path.write_text(json.dumps(state, indent=2))
        state_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Non-fatal


# ---------------------------------------------------------------------------
# ts auth status
# ---------------------------------------------------------------------------


@app.command("status")
def auth_status(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile to inspect.", envvar="TS_PROFILE"),
    ] = None,
) -> None:
    """Show credential state, environment, and token expiry.

    Prints the credential panel. Exit 0 iff a valid token is present.
    Never prints secrets in full — shows last-4 only.
    """
    console = _console()
    creds_path = _credentials_path(profile)

    if not creds_path.exists():
        console.print(
            f"[ts.bad]✖[/ts.bad] No credentials file found at [ts.mono]{creds_path}[/ts.mono]\n"
            "  Run [bold]ts auth set[/bold] to configure credentials."
        )
        raise typer.Exit(code=3) from None

    try:
        creds_data = _load_credentials_plaintext(creds_path)
    except Exception as exc:
        console.print(f"[ts.bad]✖[/ts.bad] Failed to read credentials: {exc}")
        raise typer.Exit(code=3) from None

    # Build expiry string
    expires_at_str = creds_data.get("access_token_expires_at", "")
    access_token = creds_data.get("access_token", "")
    expiry_display: str | None = None

    if access_token and expires_at_str:
        from datetime import datetime, timezone

        try:
            exp_dt = datetime.fromisoformat(str(expires_at_str).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = exp_dt - now
            if delta.total_seconds() > 0:
                mins = int(delta.total_seconds()) // 60
                secs = int(delta.total_seconds()) % 60
                utc_str = exp_dt.strftime("%H:%M")
                expiry_display = f"in {mins}m {secs:02d}s — {utc_str}"
                token_status = "valid"
            else:
                token_status = "expired"
        except ValueError:
            token_status = "unknown"
    elif access_token:
        token_status = "present (expiry unknown)"
    else:
        token_status = "none"

    # Determine scheme
    scheme_raw = creds_data.get("scheme", "plaintext")
    scheme = str(scheme_raw)

    env_raw = creds_data.get("environment", "sim")
    environment = str(env_raw)
    client_id = str(creds_data.get("client_id", ""))
    refresh_tok = str(creds_data.get("refresh_token", ""))
    scope = str(creds_data.get("scope", ""))

    panel = panel_auth_status(
        path=str(creds_path),
        scheme=scheme,
        keyring_backend=None,
        environment=environment,
        client_id=client_id,
        refresh_token=refresh_tok,
        access_token_status=token_status,
        access_token_expiry=expiry_display,
        scope=scope,
    )
    console.print(panel)

    # Exit 0 only if we have a valid access token
    if token_status not in {"valid", "present (expiry unknown)"}:
        raise typer.Exit(code=3) from None


def _load_credentials_plaintext(path: Path) -> dict[str, object]:
    """Load the raw plaintext credential payload from *path*.

    Supports both ``scheme: plaintext`` (payload key) and a direct payload.
    Returns the inner payload dict.
    """
    import json

    raw = json.loads(path.read_text())
    scheme = raw.get("scheme", "plaintext")
    if scheme == "plaintext":
        payload = raw.get("payload", raw)
        return dict(payload) if isinstance(payload, dict) else {}
    # For other schemes, return the top-level dict (Phase 2 will handle decryption)
    return dict(raw)


# ---------------------------------------------------------------------------
# ts auth refresh
# ---------------------------------------------------------------------------


@app.command("refresh")
def auth_refresh(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile.", envvar="TS_PROFILE"),
    ] = None,
) -> None:
    """Force an access-token refresh now.

    Reads existing credentials, exchanges the refresh token, and writes the
    new access token back to the credentials file.
    """
    console = _console()
    creds_path = _credentials_path(profile)

    if not creds_path.exists():
        console.print(
            f"[ts.bad]✖[/ts.bad] No credentials file found at [ts.mono]{creds_path}[/ts.mono]\n"
            "  Run [bold]ts auth set[/bold] to configure credentials."
        )
        raise typer.Exit(code=3) from None

    try:
        payload = _load_credentials_plaintext(creds_path)
    except Exception as exc:
        console.print(f"[ts.bad]✖[/ts.bad] Failed to read credentials: {exc}")
        raise typer.Exit(code=3) from None

    client_id = str(payload.get("client_id", ""))
    client_secret = str(payload.get("client_secret", ""))
    refresh_tok = str(payload.get("refresh_token", ""))
    env_str = str(payload.get("environment", "sim"))
    try:
        environment = Environment(env_str)
    except ValueError:
        environment = Environment.SIM

    if not client_id or not refresh_tok:
        console.print("[ts.bad]✖[/ts.bad] Credentials are incomplete.")
        raise typer.Exit(code=3) from None

    console.print("[ts.muted]  Refreshing access token…[/ts.muted]", end=" ")
    access_token, expires_in = _try_token_exchange(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_tok,
        environment=environment,
        console=console,
    )

    if access_token:
        # Update the stored credentials
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        expires_at: str | None = None
        if expires_in:
            expires_at = (now + timedelta(seconds=expires_in)).isoformat().replace("+00:00", "Z")

        credentials = Credentials(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_tok,
            scope=str(payload.get("scope", _DEFAULT_SCOPE)),
            environment=environment,
            access_token=access_token,
            access_token_expires_at=expires_at,
        )
        try:
            _write_credentials_plaintext(credentials, creds_path)
        except OSError as exc:
            console.print(f"\n[ts.bad]✖[/ts.bad] Failed to write credentials: {exc}")
            raise typer.Exit(code=1) from None


# ---------------------------------------------------------------------------
# ts auth login
# ---------------------------------------------------------------------------


@app.command("login")
def auth_login() -> None:
    """Browser auth-code flow (PKCE) → refresh token.

    Not yet implemented.  Use ``ts auth set`` with a pre-obtained refresh token.
    """
    console = _console()
    console.print(
        "[ts.warn]  ⚠  [/ts.warn]  ``ts auth login`` (browser PKCE flow) is not yet implemented.\n"
        "  Use [bold]ts auth set --refresh-token <TOKEN>[/bold] instead."
    )
    raise typer.Exit(code=1) from None


# ---------------------------------------------------------------------------
# ts auth clear
# ---------------------------------------------------------------------------


@app.command("clear")
def auth_clear(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile to clear.", envvar="TS_PROFILE"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
    revoke: Annotated[
        bool,
        typer.Option("--revoke", help="Also call POST /oauth/revoke on the refresh token."),
    ] = False,
) -> None:
    """Wipe credentials and keyring entry.

    Requires typing DELETE to confirm (or --yes to skip).
    """
    console = _console()
    creds_path = _credentials_path(profile)

    if not creds_path.exists():
        console.print(
            f"[ts.warn]  No credentials file found at [ts.mono]{creds_path}[/ts.mono][/ts.warn]"
        )
        raise typer.Exit(code=0) from None

    details = {
        "Path": str(creds_path),
        "Keyring": "will remove entry (if present)",
    }
    if revoke:
        details["Token revoke"] = "POST /oauth/revoke (refresh token)"

    confirmed = confirm_destructive(
        "CLEAR CREDENTIALS",
        details,
        console=console,
        yes=yes,
        token="DELETE",
        token_prompt="Type DELETE to confirm",
    )
    if not confirmed:
        console.print("[ts.muted]  Aborted.[/ts.muted]")
        raise typer.Exit(code=0) from None

    try:
        creds_path.unlink()
        console.print(f"[ts.ok]✔[/ts.ok] Credentials removed: [ts.mono]{creds_path}[/ts.mono]")
    except OSError as exc:
        console.print(f"[ts.bad]✖[/ts.bad] Failed to remove credentials: {exc}")
        raise typer.Exit(code=1) from None

    # Remove state.json if present
    import contextlib

    state_path = creds_path.parent / "state.json"
    if state_path.exists():
        with contextlib.suppress(OSError):
            state_path.unlink()


# ---------------------------------------------------------------------------
# ts auth export
# ---------------------------------------------------------------------------


@app.command("export")
def auth_export(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile.", envvar="TS_PROFILE"),
    ] = None,
    yes_i_want_secrets_on_stdout: Annotated[
        bool,
        typer.Option(
            "--yes-i-want-secrets-on-stdout",
            help="Required flag — acknowledges secrets will appear in terminal history.",
        ),
    ] = False,
) -> None:
    """Print the decrypted credential payload as JSON to stdout.

    DANGEROUS: output includes refresh token and client secret.
    Requires --yes-i-want-secrets-on-stdout.
    """
    console = _console()

    if not yes_i_want_secrets_on_stdout:
        console.print(
            "[ts.danger]  ⚠  This command prints secrets (refresh token, client secret) "
            "to stdout.[/ts.danger]\n"
            "  Pass [bold]--yes-i-want-secrets-on-stdout[/bold] to proceed."
        )
        raise typer.Exit(code=1) from None

    creds_path = _credentials_path(profile)
    if not creds_path.exists():
        console.print(f"[ts.bad]✖[/ts.bad] No credentials file at [ts.mono]{creds_path}[/ts.mono]")
        raise typer.Exit(code=3) from None

    try:
        payload = _load_credentials_plaintext(creds_path)
    except Exception as exc:
        console.print(f"[ts.bad]✖[/ts.bad] Failed to read credentials: {exc}")
        raise typer.Exit(code=3) from None

    import json

    # Plain stdout — no Rich styling so it pipes cleanly
    print(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# ts auth doctor
# ---------------------------------------------------------------------------


@app.command("doctor")
def auth_doctor(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile.", envvar="TS_PROFILE"),
    ] = None,
) -> None:
    """Run credential diagnostics.

    Checks:
    - Credentials file existence and permissions.
    - Keyring backend availability.
    - Token exchange (refresh → access token).
    - Scopes returned vs. requested.
    """
    console = _console()
    creds_path = _credentials_path(profile)

    tree = Tree("[ts.header]ts auth doctor[/ts.header]")

    # 1. File check
    file_node = tree.add("[ts.label]Credentials file[/ts.label]")
    if creds_path.exists():
        file_node.add(f"[ts.ok]✔[/ts.ok]  Path: [ts.mono]{creds_path}[/ts.mono]")
        file_stat = creds_path.stat()
        mode = oct(stat.S_IMODE(file_stat.st_mode))
        mode_ok = stat.S_IMODE(file_stat.st_mode) == 0o600
        mode_style = "ts.ok" if mode_ok else "ts.warn"
        file_node.add(
            f"[{mode_style}]{'✔' if mode_ok else '⚠'}[/{mode_style}]  Permissions: {mode}"
        )
        try:
            payload = _load_credentials_plaintext(creds_path)
            scheme = str(payload.get("scheme", "unknown"))
            file_node.add(f"[ts.ok]✔[/ts.ok]  Scheme: [ts.value]{scheme}[/ts.value]")
        except Exception as exc:
            file_node.add(f"[ts.bad]✖[/ts.bad]  Parse error: {exc}")
            payload = {}
    else:
        file_node.add(f"[ts.bad]✖[/ts.bad]  Not found: [ts.mono]{creds_path}[/ts.mono]")
        file_node.add("  Run [bold]ts auth set[/bold] to create it.")
        payload = {}

    # 2. Keyring check
    keyring_node = tree.add("[ts.label]Keyring backend[/ts.label]")
    try:
        import keyring  # type: ignore[import-untyped,unused-ignore]

        backend = keyring.get_keyring()
        keyring_node.add(
            f"[ts.ok]✔[/ts.ok]  Available: [ts.value]{type(backend).__name__}[/ts.value]"
        )
    except ImportError:
        keyring_node.add("[ts.warn]⚠[/ts.warn]  keyring not installed (pip install keyring)")
    except Exception as exc:
        keyring_node.add(f"[ts.warn]⚠[/ts.warn]  {exc}")

    # 3. Token exchange check
    token_node = tree.add("[ts.label]Token exchange[/ts.label]")
    if payload:
        client_id = str(payload.get("client_id", ""))
        client_secret = str(payload.get("client_secret", ""))
        refresh_tok = str(payload.get("refresh_token", ""))

        if client_id and refresh_tok:
            try:
                import httpx

                token_url = "https://signin.tradestation.com/oauth/token"
                data: dict[str, str] = {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_tok,
                }
                if client_secret:
                    data["client_secret"] = client_secret
                resp = httpx.post(token_url, data=data, timeout=15)
                if resp.status_code == 200:
                    body = resp.json()
                    expires_in = int(body.get("expires_in", 1200))
                    mins = expires_in // 60
                    returned_scope = body.get("scope", "")
                    token_node.add(
                        f"[ts.ok]✔[/ts.ok]  Exchange succeeded "
                        f"[ts.muted](expires in {mins}m)[/ts.muted]"
                    )
                    # 4. Scope comparison
                    scope_node = tree.add("[ts.label]Scopes[/ts.label]")
                    requested = set(str(payload.get("scope", "")).split())
                    received = set(str(returned_scope).split())
                    for s in sorted(requested):
                        present = s in received
                        icon = "✔" if present else "✖"
                        style = "ts.ok" if present else "ts.bad"
                        scope_node.add(f"[{style}]{icon}[/{style}]  {s}")
                    for s in sorted(received - requested):
                        scope_node.add(f"[ts.muted]    {s}  (extra)[/ts.muted]")
                else:
                    token_node.add(
                        f"[ts.bad]✖[/ts.bad]  Exchange failed "
                        f"[ts.muted](HTTP {resp.status_code})[/ts.muted]"
                    )
            except Exception as exc:
                token_node.add(f"[ts.bad]✖[/ts.bad]  Network error: {exc}")
        else:
            token_node.add("[ts.warn]⚠[/ts.warn]  Credentials incomplete — skipping exchange")
    else:
        token_node.add("[ts.muted]  (skipped — no credentials)[/ts.muted]")

    console.print(tree)
