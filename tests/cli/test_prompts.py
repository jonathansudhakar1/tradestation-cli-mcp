"""Tests for prompts.py — confirmation flows."""

from __future__ import annotations

import io

from rich.console import Console

from tradestation.cli.prompts import ask_confirm, ask_typed_token, confirm_destructive
from tradestation.cli.theme import get_theme


def _console() -> Console:
    buf = io.StringIO()
    return Console(file=buf, force_terminal=True, no_color=True, theme=get_theme())


class TestAskConfirm:
    def test_yes_flag_bypasses_prompt(self) -> None:
        """ask_confirm with yes=True should return True without any input."""
        console = _console()
        result = ask_confirm("Continue?", console=console, yes=True)
        assert result is True

    def test_default_false_with_empty_input(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Empty input with default=False should return False."""
        monkeypatch.setattr("builtins.input", lambda: "")
        console = _console()
        result = ask_confirm("Continue?", console=console, default=False)
        assert result is False

    def test_default_true_with_empty_input(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Empty input with default=True should return True."""
        monkeypatch.setattr("builtins.input", lambda: "")
        console = _console()
        result = ask_confirm("Continue?", console=console, default=True)
        assert result is True

    def test_y_input_returns_true(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Input 'y' should return True."""
        monkeypatch.setattr("builtins.input", lambda: "y")
        console = _console()
        result = ask_confirm("Continue?", console=console)
        assert result is True

    def test_yes_input_returns_true(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Input 'yes' should return True."""
        monkeypatch.setattr("builtins.input", lambda: "yes")
        console = _console()
        result = ask_confirm("Continue?", console=console)
        assert result is True

    def test_n_input_returns_false(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Input 'n' should return False."""
        monkeypatch.setattr("builtins.input", lambda: "n")
        console = _console()
        result = ask_confirm("Continue?", console=console)
        assert result is False

    def test_eof_returns_false(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """EOFError (piped stdin exhausted) should return False."""
        def raise_eof() -> str:
            raise EOFError()

        monkeypatch.setattr("builtins.input", raise_eof)
        console = _console()
        result = ask_confirm("Continue?", console=console)
        assert result is False


class TestAskTypedToken:
    def test_yes_flag_bypasses_prompt(self) -> None:
        """ask_typed_token with yes=True returns True without input."""
        console = _console()
        result = ask_typed_token("DELETE", prompt="Type DELETE", console=console, yes=True)
        assert result is True

    def test_correct_token_returns_true(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Correct token returns True."""
        monkeypatch.setattr("builtins.input", lambda: "DELETE")
        console = _console()
        result = ask_typed_token("DELETE", prompt="Type DELETE", console=console)
        assert result is True

    def test_wrong_token_returns_false(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Wrong token returns False."""
        monkeypatch.setattr("builtins.input", lambda: "delete")
        console = _console()
        result = ask_typed_token("DELETE", prompt="Type DELETE", console=console)
        assert result is False

    def test_empty_token_returns_false(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Empty input returns False."""
        monkeypatch.setattr("builtins.input", lambda: "")
        console = _console()
        result = ask_typed_token("DELETE", prompt="Type DELETE", console=console)
        assert result is False

    def test_eof_returns_false(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """EOFError returns False."""
        def raise_eof() -> str:
            raise EOFError()

        monkeypatch.setattr("builtins.input", raise_eof)
        console = _console()
        result = ask_typed_token("DELETE", prompt="Type DELETE", console=console)
        assert result is False


class TestConfirmDestructive:
    def test_yes_flag_bypasses_prompt(self) -> None:
        """confirm_destructive with yes=True returns True without display."""
        console = _console()
        result = confirm_destructive(
            "CANCEL ORDER",
            {"Order": "835711", "Detail": "AAPL BUY 100"},
            console=console,
            yes=True,
        )
        assert result is True

    def test_displays_panel_with_details(self) -> None:
        """confirm_destructive should display a panel with the provided details."""
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=True, no_color=True, theme=get_theme())

        def mock_input() -> str:
            return ""

        import unittest.mock

        with unittest.mock.patch("builtins.input", return_value=""):
            confirm_destructive(
                "CANCEL ORDER",
                {"Order": "835711"},
                console=console,
            )

        output = buf.getvalue()
        assert "CANCEL ORDER" in output or "835711" in output

    def test_token_confirmation_required(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """With token= set, correct token should return True."""
        monkeypatch.setattr("builtins.input", lambda: "DELETE")
        console = _console()
        result = confirm_destructive(
            "CLEAR CREDENTIALS",
            {"Path": "/tmp/creds"},
            console=console,
            token="DELETE",
        )
        assert result is True

    def test_wrong_token_returns_false(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Wrong token returns False."""
        monkeypatch.setattr("builtins.input", lambda: "WRONG")
        console = _console()
        result = confirm_destructive(
            "CLEAR CREDENTIALS",
            {"Path": "/tmp/creds"},
            console=console,
            token="DELETE",
        )
        assert result is False
