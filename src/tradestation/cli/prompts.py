"""Confirmation prompts for destructive CLI actions.

See docs/07-output-style.md §"Confirmation prompts (destructive actions)".

Usage::

    from tradestation.cli.prompts import ask_confirm, ask_typed_token
    from rich.console import Console

    console = Console()

    # Simple yes/no (respects --yes flag)
    if not ask_confirm("Proceed?", console=console, yes=False):
        raise typer.Abort()

    # Typed-token confirmation (order cancel, auth clear)
    if not ask_typed_token("DELETE", prompt="Type DELETE to confirm", console=console):
        raise typer.Abort()
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def ask_confirm(
    message: str,
    *,
    console: Console,
    yes: bool = False,
    default: bool = False,
) -> bool:
    """Ask a yes/no confirmation question.

    Args:
        message: The question to display.
        console: Rich ``Console`` to use for output.
        yes: If ``True``, skip the prompt and return ``True`` immediately
            (honours the global ``--yes`` flag).
        default: Default answer when the user presses Enter without typing.

    Returns:
        ``True`` if the user confirmed, ``False`` otherwise.
    """
    if yes:
        return True

    suffix = " [bold][Y/n][/bold]" if default else " [bold][y/N][/bold]"
    console.print(message + suffix, end=" ")
    try:
        raw = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if not raw:
        return default
    return raw in {"y", "yes"}


def ask_typed_token(
    expected: str,
    *,
    prompt: str,
    console: Console,
    yes: bool = False,
) -> bool:
    """Prompt the user to type a specific token to confirm a destructive action.

    Args:
        expected: The exact string the user must type (e.g. ``"DELETE"``).
        prompt: Prompt text displayed before the input field.
        console: Rich ``Console`` for output.
        yes: If ``True``, skip the prompt and return ``True`` immediately.

    Returns:
        ``True`` if the user typed the expected token, ``False`` otherwise.
    """
    if yes:
        return True

    console.print(f"\n  {prompt}: ", end="")
    try:
        raw = input().strip()
    except (EOFError, KeyboardInterrupt):
        return False

    return raw == expected


def confirm_destructive(
    title: str,
    details: dict[str, str],
    *,
    console: Console,
    yes: bool = False,
    token: str | None = None,
    token_prompt: str | None = None,
) -> bool:
    """Show a destructive-action confirmation panel and prompt.

    Renders a bordered warning panel with the action title and detail rows,
    then either asks a typed-token confirmation or a simple yes/no.

    See docs/07-output-style.md §"Confirmation prompts (destructive actions)".

    Args:
        title: Action title shown in the panel (e.g. ``"CANCEL ORDER"``).
        details: Ordered dict of ``{label: value}`` rows shown in the panel.
        console: Rich ``Console`` for output.
        yes: Honour ``--yes`` flag — skip prompts and return ``True``.
        token: If supplied, require the user to type this exact string.
        token_prompt: Custom text before the typed-token input field.

    Returns:
        ``True`` if the user confirmed, ``False`` otherwise.
    """
    if yes:
        return True

    # Build the panel body
    lines: list[str] = [f"[ts.danger]  ⚠  {title}[/ts.danger]", ""]
    for label, value in details.items():
        lines.append(f"  [ts.label]{label:<14}[/ts.label]  [ts.value]{value}[/ts.value]")

    body_text = Text.from_markup("\n".join(lines))
    panel = Panel(
        body_text,
        border_style="ts.danger",
        expand=False,
    )
    console.print(panel)

    if token is not None:
        prompt_text = token_prompt or f"Type [ts.kbd]{token}[/ts.kbd] to confirm"
        return ask_typed_token(token, prompt=prompt_text, console=console, yes=False)

    return ask_confirm("Proceed?", console=console, yes=False, default=False)


def prompt_secret(prompt_text: str, *, console: Console) -> str:
    """Prompt for a secret value with masked (password) input.

    Args:
        prompt_text: Label shown before the prompt (e.g. ``"Client ID"``).
        console: Rich ``Console`` for output (used for the label; input via
            :func:`typer.prompt` to get masking).

    Returns:
        The entered secret string (may be empty).
    """
    return str(
        typer.prompt(
            prompt_text,
            hide_input=True,
            default="",
            show_default=False,
            prompt_suffix=" > ",
        )
    )


def prompt_text(prompt_text: str, *, default: str = "", console: Console) -> str:
    """Prompt for a plain-text value.

    Args:
        prompt_text: Label shown before the prompt.
        default: Default value (displayed in brackets).
        console: Rich ``Console`` (unused directly; kept for API symmetry).

    Returns:
        The entered string, or *default* if the user pressed Enter.
    """
    return str(
        typer.prompt(
            prompt_text,
            default=default,
            show_default=bool(default),
            prompt_suffix=" > ",
        )
    )
