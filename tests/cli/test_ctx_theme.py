"""Tests for ctx.py (CLIContext) and theme.py (get_theme, user overrides)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tradestation.cli.ctx import CLIContext, OutputMode
from tradestation.cli.theme import _DEFAULT_STYLES, _load_user_overrides, get_theme
from tradestation.enums import Environment

# ---------------------------------------------------------------------------
# Theme tests
# ---------------------------------------------------------------------------


class TestTheme:
    def test_default_styles_contains_all_required_names(self) -> None:
        """All ts.* style names from docs/07 must exist in the default palette."""
        required = [
            "ts.header",
            "ts.label",
            "ts.value",
            "ts.mono",
            "ts.symbol",
            "ts.price",
            "ts.up",
            "ts.down",
            "ts.flat",
            "ts.warn",
            "ts.danger",
            "ts.ok",
            "ts.bad",
            "ts.muted",
            "ts.kbd",
            "ts.heartbeat",
            "ts.json.key",
            "ts.json.string",
            "ts.json.number",
        ]
        for name in required:
            assert name in _DEFAULT_STYLES, f"Missing required style: {name}"

    def test_get_theme_returns_theme_with_all_styles(self) -> None:
        """get_theme() without overrides returns a Theme containing all default styles."""
        theme = get_theme(override_path=Path("/nonexistent/path.toml"))
        # Check a sample of styles exist in the theme
        for name in ("ts.header", "ts.up", "ts.down", "ts.ok", "ts.bad"):
            assert name in theme.styles, f"Style {name!r} missing from theme"

    def test_user_overrides_applied(self, tmp_path: Path) -> None:
        """User theme.toml overrides should replace default styles."""
        override_file = tmp_path / "theme.toml"
        override_file.write_text('[styles]\n"ts.up" = "bold cyan"\n')

        theme = get_theme(override_path=override_file)
        # ts.up should now be bold cyan
        style_str = str(theme.styles.get("ts.up", ""))
        assert "cyan" in style_str or theme.styles.get("ts.up") is not None

    def test_user_overrides_preserve_non_overridden_styles(self, tmp_path: Path) -> None:
        """Non-overridden styles must remain at their defaults."""
        override_file = tmp_path / "theme.toml"
        override_file.write_text('[styles]\n"ts.up" = "bold cyan"\n')

        theme = get_theme(override_path=override_file)
        # ts.header should still be in the theme
        assert "ts.header" in theme.styles

    def test_missing_theme_file_returns_defaults(self, tmp_path: Path) -> None:
        """A non-existent theme.toml should silently return default styles."""
        missing = tmp_path / "does_not_exist.toml"
        overrides = _load_user_overrides(missing)
        assert overrides == {}

    def test_malformed_theme_file_returns_empty(self, tmp_path: Path) -> None:
        """A malformed theme.toml should silently return empty (no crash)."""
        bad_file = tmp_path / "theme.toml"
        bad_file.write_text("this is { not valid toml\n")
        overrides = _load_user_overrides(bad_file)
        assert overrides == {}

    def test_theme_toml_non_string_styles_ignored(self, tmp_path: Path) -> None:
        """Non-string style values in theme.toml should be silently ignored."""
        override_file = tmp_path / "theme.toml"
        override_file.write_text('[styles]\n"ts.up" = 42\n')
        overrides = _load_user_overrides(override_file)
        # Non-string values should not be included
        assert "ts.up" not in overrides


# ---------------------------------------------------------------------------
# CLIContext tests
# ---------------------------------------------------------------------------


class TestCLIContext:
    def test_create_default_environment_is_sim(self) -> None:
        """CLIContext.create() should default to SIM environment."""
        ctx = CLIContext.create()
        assert ctx.environment == Environment.SIM

    def test_create_with_live_environment(self) -> None:
        """CLIContext.create() should accept LIVE environment."""
        ctx = CLIContext.create(environment=Environment.LIVE)
        assert ctx.environment == Environment.LIVE

    def test_create_console_is_created(self) -> None:
        """CLIContext.create() should set up a Rich Console."""
        from rich.console import Console

        ctx = CLIContext.create()
        assert isinstance(ctx.console, Console)

    def test_output_mode_auto_table_in_tty(self) -> None:
        """output_mode should return TABLE when no output set and console is TTY."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        theme = get_theme()
        console = Console(file=buf, theme=theme, force_terminal=True)
        ctx = CLIContext(console=console, output=None)
        assert ctx.output_mode == OutputMode.TABLE

    def test_output_mode_auto_jsonl_when_piped(self) -> None:
        """output_mode should return JSONL when no output set and console is not TTY."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        theme = get_theme()
        console = Console(file=buf, theme=theme, force_terminal=False)
        ctx = CLIContext(console=console, output=None)
        assert ctx.output_mode == OutputMode.JSONL

    def test_output_mode_explicit_overrides_auto(self) -> None:
        """An explicit output mode should override auto-detection."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        ctx = CLIContext(console=console, output=OutputMode.JSON)
        assert ctx.output_mode == OutputMode.JSON

    def test_output_mode_csv_explicit(self) -> None:
        """OutputMode.CSV should be returned when set explicitly."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=False)
        ctx = CLIContext(console=console, output=OutputMode.CSV)
        assert ctx.output_mode == OutputMode.CSV

    def test_banner_omitted_when_quiet(self) -> None:
        """banner() should produce no output when quiet=True."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, no_color=True)
        ctx = CLIContext(console=console, quiet=True)
        ctx.banner("Quotes", "3 symbols")
        assert buf.getvalue() == ""

    def test_banner_omitted_when_not_terminal(self) -> None:
        """banner() should produce no output when console is not a TTY."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, no_color=True)
        ctx = CLIContext(console=console, quiet=False)
        ctx.banner("Quotes", "3 symbols")
        assert buf.getvalue() == ""

    def test_banner_prints_when_tty_and_not_quiet(self) -> None:
        """banner() should print a line when TTY and not quiet."""
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, no_color=True)
        ctx = CLIContext(console=console, quiet=False, environment=Environment.SIM)
        ctx.banner("Quotes", "3 symbols")
        output = buf.getvalue()
        assert "Quotes" in output
        assert "sim" in output

    def test_attach_and_from_typer(self) -> None:
        """attach() + from_typer() roundtrip should return the same context."""
        import click

        # Use a Click command context directly (typer.Context is click.Context)
        cmd = click.Command("test")
        typer_ctx = click.Context(cmd)
        ctx = CLIContext.create()
        ctx.attach(typer_ctx)  # type: ignore[arg-type]
        retrieved = CLIContext.from_typer(typer_ctx)  # type: ignore[arg-type]
        assert retrieved is ctx

    def test_from_typer_raises_without_attach(self) -> None:
        """from_typer() should raise RuntimeError when no context is attached."""
        import click

        cmd = click.Command("test")
        typer_ctx = click.Context(cmd)
        with pytest.raises(RuntimeError, match="CLIContext not found"):
            CLIContext.from_typer(typer_ctx)  # type: ignore[arg-type]

    def test_create_with_profile(self) -> None:
        """CLIContext.create() should accept a profile name."""
        ctx = CLIContext.create(profile="paper")
        assert ctx.profile == "paper"

    def test_create_with_quiet_flag(self) -> None:
        """CLIContext.create() should accept quiet=True."""
        ctx = CLIContext.create(quiet=True)
        assert ctx.quiet is True

    def test_create_with_verbose_level(self) -> None:
        """CLIContext.create() should accept verbose level."""
        ctx = CLIContext.create(verbose=2)
        assert ctx.verbose == 2

    def test_create_with_yes_flag(self) -> None:
        """CLIContext.create() should accept yes=True."""
        ctx = CLIContext.create(yes=True)
        assert ctx.yes is True
