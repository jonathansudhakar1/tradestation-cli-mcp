"""Shared CLI context object stashed on the Typer/Click context.

``CLIContext`` holds all per-invocation state:
- Active Rich ``Console`` (themed, with TTY/no-color awareness).
- The lazily-constructed ``TradeStationClient``.
- Output mode, environment, profile name, verbosity, quiet flag.

Default environment is **SIM** per project conventions.

Usage in a command::

    import typer
    from tradestation.cli.ctx import CLIContext, pass_cli_ctx


    @app.command()
    def my_cmd(ctx: typer.Context) -> None:
        cli = CLIContext.from_typer(ctx)
        cli.console.print("hello")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from tradestation.cli.theme import get_theme
from tradestation.enums import Environment

if TYPE_CHECKING:
    from tradestation.client import TradeStationClient


class OutputMode(str, Enum):
    """Rendering mode for command output."""

    TABLE = "table"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    TSV = "tsv"
    YAML = "yaml"


#: Key used to store CLIContext on the Typer/Click context object.
_CTX_KEY = "cli_context"


@dataclass
class CLIContext:
    """Per-invocation CLI state.

    Attributes:
        console: Rich ``Console`` configured with the active theme and
            color/quiet settings.
        environment: API environment override for this invocation.
            Defaults to :attr:`~tradestation.enums.Environment.SIM`.
        profile: Named profile (``~/.tscli/profiles/<name>``).
            ``None`` means the default profile.
        output: Rendering mode.  When ``None`` it is auto-detected:
            TTY → ``table``; piped → ``jsonl``.
        quiet: Suppress non-data output (banners, spinners, progress).
        verbose: Verbosity level (0 = default, 1 = -v, 2 = -vv).
        unsafe_log_secrets: Disable token/secret redaction in logs.
        timeout: Per-request HTTP timeout in seconds.
        retries: Retry budget for transient failures.
        yes: Skip confirmation prompts (behave as if user answered yes).
        _client: Lazily constructed ``TradeStationClient`` — access via
            :meth:`client`.
    """

    console: Console
    environment: Environment = Environment.SIM
    profile: str | None = None
    output: OutputMode | None = None
    quiet: bool = False
    verbose: int = 0
    unsafe_log_secrets: bool = False
    timeout: float = 30.0
    retries: int = 3
    yes: bool = False
    _client: TradeStationClient | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Constructor helpers
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        environment: Environment = Environment.SIM,
        profile: str | None = None,
        output: OutputMode | None = None,
        no_color: bool = False,
        quiet: bool = False,
        verbose: int = 0,
        unsafe_log_secrets: bool = False,
        timeout: float = 30.0,
        retries: int = 3,
        yes: bool = False,
        theme_path: str | None = None,
    ) -> CLIContext:
        """Build a :class:`CLIContext` from global-flag values.

        Args:
            environment: Environment for this invocation (default: SIM).
            profile: Named profile directory under ``~/.tscli/profiles/``.
            output: Output rendering mode.  ``None`` = auto-detect from TTY.
            no_color: Force ANSI-free output.
            quiet: Suppress non-data output.
            verbose: Verbosity level (0/1/2).
            unsafe_log_secrets: Disable redaction.
            timeout: HTTP request timeout in seconds.
            retries: Retry budget.
            yes: Skip confirmation prompts.
            theme_path: Override path for ``theme.toml`` (testing).

        Returns:
            A fully initialised :class:`CLIContext`.
        """
        from pathlib import Path

        theme = get_theme(override_path=Path(theme_path) if theme_path else None)
        console = Console(
            theme=theme,
            no_color=no_color or None,
            # Rich treats quiet as "don't print" — we handle it at a higher level.
        )
        return cls(
            console=console,
            environment=environment,
            profile=profile,
            output=output,
            quiet=quiet,
            verbose=verbose,
            unsafe_log_secrets=unsafe_log_secrets,
            timeout=timeout,
            retries=retries,
            yes=yes,
        )

    # ------------------------------------------------------------------
    # Typer context integration
    # ------------------------------------------------------------------

    def attach(self, typer_ctx: typer.Context) -> None:
        """Stash *self* on the Typer context so sub-commands can retrieve it."""
        typer_ctx.ensure_object(dict)
        typer_ctx.obj[_CTX_KEY] = self

    @classmethod
    def from_typer(cls, typer_ctx: typer.Context) -> CLIContext:
        """Retrieve the :class:`CLIContext` stored on *typer_ctx*.

        Raises:
            RuntimeError: If no context has been attached (bug in command wiring).
        """
        obj = typer_ctx.obj
        if not isinstance(obj, dict) or _CTX_KEY not in obj:
            raise RuntimeError(
                "CLIContext not found on Typer context — "
                "did you forget the --env/--sim/--profile callback?"
            )
        ctx: CLIContext = obj[_CTX_KEY]
        return ctx

    # ------------------------------------------------------------------
    # Lazy client
    # ------------------------------------------------------------------

    @property
    def client(self) -> TradeStationClient:
        """Return the lazily-constructed :class:`~tradestation.client.TradeStationClient`.

        On first access, loads credentials from disk (or profile), falling back
        to environment variables when no credentials file exists.  Subsequent
        accesses return the cached instance.

        Raises:
            tradestation.errors.NoCredentialsError: If no credentials are found
                anywhere (file or env vars).
        """
        if self._client is None:
            from tradestation.client import TradeStationClient
            from tradestation.errors import NoCredentialsError

            if self.profile:
                self._client = TradeStationClient.from_profile(
                    self.profile,
                    timeout=self.timeout,
                    retries=self.retries,
                )
            else:
                try:
                    self._client = TradeStationClient.from_default_credentials(
                        timeout=self.timeout,
                        retries=self.retries,
                        environment=self.environment,
                    )
                except NoCredentialsError:
                    # Fall back to environment variables (CI / .env workflows)
                    self._client = TradeStationClient.from_env(
                        timeout=self.timeout,
                        retries=self.retries,
                    )
        return self._client

    # ------------------------------------------------------------------
    # Resolved output mode
    # ------------------------------------------------------------------

    @property
    def output_mode(self) -> OutputMode:
        """Return the effective output mode, auto-detecting from TTY when unset."""
        if self.output is not None:
            return self.output
        if self.console.is_terminal:
            return OutputMode.TABLE
        return OutputMode.JSONL

    # ------------------------------------------------------------------
    # Banner helper
    # ------------------------------------------------------------------

    def banner(self, operation: str, scope: str = "") -> None:
        """Print a one-line context banner (omitted under --quiet or piped).

        Format: ``{operation}  •  {scope}  •  {environment}  •  {time} UTC``
        """
        if self.quiet or not self.console.is_terminal:
            return
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        parts = [operation]
        if scope:
            parts.append(scope)
        parts.append(self.environment.value)
        parts.append(f"{now} UTC")
        line = "  [ts.muted]•[/ts.muted]  ".join(f"[ts.header]{p}[/ts.header]" for p in parts)
        self.console.print(line)
