"""``ts auth`` command group — credential management.

Subcommands (Phase 2 implementation):
    set      — interactive / non-interactive credential setup
    status   — show credential health and expiry
    refresh  — force an immediate token refresh
    login    — browser OAuth code-grant flow (PKCE)
    clear    — wipe credentials (with confirmation)
    export   — print decrypted payload (dangerous; requires --yes flag)
    doctor   — diagnostics (keyring, token exchange, scopes)

See docs/02-auth-and-credentials.md for the full design.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="auth",
    help="[bold]Credential management[/bold]: set, status, refresh, login, clear, doctor.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
