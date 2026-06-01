"""``ts env`` command group — SIM ↔ LIVE environment switching.

Subcommands:
    show  — display the current default environment
    live  — switch default to LIVE (requires loud confirmation)
    sim   — switch default to SIM

Switches are persisted in ``~/.tscli/state.json``.

See docs/04-cli-design.md §"Command tree" (env section).
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from tradestation.cli.prompts import ask_confirm
from tradestation.cli.theme import get_theme
from tradestation.enums import Environment

app = typer.Typer(
    name="env",
    help="[bold]Environment switching[/bold]: show, live, sim.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

_STATE_FILENAME = "state.json"


def _console() -> Console:
    """Return a themed Rich console."""
    return Console(theme=get_theme())


def _state_path(profile: str | None = None) -> Path:
    """Return the path to state.json, respecting an optional profile."""
    if profile:
        return Path.home() / ".tscli" / "profiles" / profile / _STATE_FILENAME
    return Path.home() / ".tscli" / _STATE_FILENAME


def _read_state(path: Path) -> dict[str, object]:
    """Read and parse state.json.  Returns empty dict if absent or invalid."""
    if not path.exists():
        return {}
    try:
        return dict(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(path: Path, state: dict[str, object]) -> None:
    """Write *state* to *path*, creating parent dirs as needed (0700/0600)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# ts env show
# ---------------------------------------------------------------------------


@app.command("show")
def env_show(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile.", envvar="TS_PROFILE"),
    ] = None,
) -> None:
    """Display the current default environment (live or sim)."""
    console = _console()
    path = _state_path(profile)
    state = _read_state(path)
    env_val = str(state.get("environment", "sim"))
    try:
        environment = Environment(env_val)
    except ValueError:
        environment = Environment.SIM

    if environment == Environment.LIVE:
        console.print(
            f"[ts.warn]  ⚠  Default environment: [bold]{environment.value}[/bold] "
            "(real money)[/ts.warn]"
        )
    else:
        console.print(
            f"[ts.ok]  ✔  Default environment: [bold]{environment.value}[/bold][/ts.ok]"
        )


# ---------------------------------------------------------------------------
# ts env live
# ---------------------------------------------------------------------------


@app.command("live")
def env_live(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile.", envvar="TS_PROFILE"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation."),
    ] = False,
) -> None:
    """Switch the default environment to LIVE (real money — requires confirmation)."""
    console = _console()

    if not yes:
        console.print(
            "\n[ts.danger]  ⚠  WARNING: switching to the LIVE environment.[/ts.danger]\n"
            "  Commands will operate on your real TradeStation account.\n"
            "  Orders will use real money.\n"
        )
        confirmed = ask_confirm(
            "  Switch default to [bold]live[/bold]?",
            console=console,
            yes=False,
            default=False,
        )
        if not confirmed:
            console.print("[ts.muted]  Aborted.[/ts.muted]")
            raise typer.Exit(code=0)

    path = _state_path(profile)
    state = _read_state(path)
    state["environment"] = Environment.LIVE.value
    _write_state(path, state)

    console.print(
        f"[ts.warn]  ⚠  Default environment set to [bold]live[/bold] — "
        f"[ts.mono]{path}[/ts.mono][/ts.warn]"
    )


# ---------------------------------------------------------------------------
# ts env sim
# ---------------------------------------------------------------------------


@app.command("sim")
def env_sim(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Named profile.", envvar="TS_PROFILE"),
    ] = None,
) -> None:
    """Switch the default environment to SIM (paper trading — safe)."""
    console = _console()
    path = _state_path(profile)
    state = _read_state(path)
    state["environment"] = Environment.SIM.value
    _write_state(path, state)
    console.print(
        f"[ts.ok]  ✔  Default environment set to [bold]sim[/bold] — "
        f"[ts.mono]{path}[/ts.mono][/ts.ok]"
    )
