"""Tests for ``ts auth set`` — interactive and non-interactive forms."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer.testing

from tradestation.cli.app import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_token_exchange_success(*args: object, **kwargs: object) -> MagicMock:
    """Mock httpx.post that returns a successful token exchange."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "access_token": "FAKEACCESSTOKEN",
        "expires_in": 1200,
        "scope": "openid offline_access MarketData ReadAccount Trade",
        "refresh_token": "NEWREFRESHTOKEN",
    }
    return resp


def _fake_token_exchange_failure(*args: object, **kwargs: object) -> MagicMock:
    """Mock httpx.post that returns a 401 error."""
    resp = MagicMock()
    resp.status_code = 401
    resp.text = '{"error":"invalid_grant","error_description":"Token expired"}'
    return resp


# ---------------------------------------------------------------------------
# Non-interactive (flag-driven) form
# ---------------------------------------------------------------------------


class TestAuthSetNonInteractive:
    def test_set_writes_credentials_file(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Non-interactive set should write credentials with correct content."""
        creds_path = tmp_tscli_dir / "credentials"

        with patch("httpx.post", side_effect=_fake_token_exchange_success):
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "set",
                    "--client-id",
                    "TESTCLIENTID",
                    "--client-secret",
                    "TESTSECRET",
                    "--refresh-token",
                    "TESTREFRESHTOKEN",
                    "--env",
                    "sim",
                ],
            )

        assert result.exit_code == 0, result.output
        assert creds_path.exists()

        data = json.loads(creds_path.read_text())
        assert data["scheme"] == "plaintext"
        payload = data["payload"]
        assert payload["client_id"] == "TESTCLIENTID"
        assert payload["client_secret"] == "TESTSECRET"
        assert payload["refresh_token"] == "TESTREFRESHTOKEN"
        assert payload["environment"] == "sim"

    def test_set_file_permissions_are_0600(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Credentials file must have mode 0600."""
        creds_path = tmp_tscli_dir / "credentials"

        with patch("httpx.post", side_effect=_fake_token_exchange_success):
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "set",
                    "--client-id",
                    "TESTCLIENTID",
                    "--client-secret",
                    "TESTSECRET",
                    "--refresh-token",
                    "TESTREFRESHTOKEN",
                ],
            )

        assert result.exit_code == 0, result.output
        file_mode = stat.S_IMODE(creds_path.stat().st_mode)
        assert file_mode == 0o600, f"Expected 0600, got {oct(file_mode)}"

    def test_set_refuses_to_write_on_auth_failure(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """If token exchange fails, no credentials file should be written."""
        creds_path = tmp_tscli_dir / "credentials"

        with patch("httpx.post", side_effect=_fake_token_exchange_failure):
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "set",
                    "--client-id",
                    "BADID",
                    "--client-secret",
                    "BADSECRET",
                    "--refresh-token",
                    "BADTOKEN",
                ],
            )

        assert result.exit_code == 3
        assert not creds_path.exists(), "Should NOT write file when auth fails"

    def test_set_requires_client_id(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Empty client_id should fail before making network calls."""
        with patch("httpx.post", side_effect=_fake_token_exchange_success) as mock_post:
            # Provide all flags but client-id as empty string
            cli_runner.invoke(
                app,
                [
                    "auth",
                    "set",
                    "--client-id",
                    "",
                    "--client-secret",
                    "SECRET",
                    "--refresh-token",
                    "TOKEN",
                ],
            )
        # Should fail — either exits 1 or prompts interactively
        # The key assertion: no file was written
        creds_path = tmp_tscli_dir / "credentials"
        assert not creds_path.exists()
        mock_post.assert_not_called()

    def test_set_no_encrypt_requires_risk_flag(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """--no-encrypt without --i-understand-the-risk should fail."""
        result = cli_runner.invoke(
            app,
            [
                "auth",
                "set",
                "--client-id",
                "ID",
                "--client-secret",
                "SECRET",
                "--refresh-token",
                "TOKEN",
                "--no-encrypt",
            ],
        )
        assert result.exit_code == 1

    def test_set_stores_access_token(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Successful set should store the access token returned by exchange."""
        creds_path = tmp_tscli_dir / "credentials"

        with patch("httpx.post", side_effect=_fake_token_exchange_success):
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "set",
                    "--client-id",
                    "ID",
                    "--client-secret",
                    "SECRET",
                    "--refresh-token",
                    "TOKEN",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(creds_path.read_text())["payload"]
        assert payload["access_token"] == "FAKEACCESSTOKEN"
        assert payload["access_token_expires_at"] is not None

    def test_set_prints_success_message(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Successful set should print a ✔ confirmation."""
        with patch("httpx.post", side_effect=_fake_token_exchange_success):
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "set",
                    "--client-id",
                    "ID",
                    "--client-secret",
                    "SECRET",
                    "--refresh-token",
                    "TOKEN",
                ],
            )
        assert result.exit_code == 0
        assert "✔" in result.output or "Saved" in result.output


# ---------------------------------------------------------------------------
# Interactive form (stdin input)
# ---------------------------------------------------------------------------


class TestAuthSetInteractive:
    def test_set_interactive_prompts_and_writes(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Interactive set reads from stdin and writes credentials."""
        creds_path = tmp_tscli_dir / "credentials"
        # Simulate user typing: client_id, client_secret, refresh_token, scope, env, encrypt
        stdin = "INTERACTIVEID\nINTERACTIVESECRET\nINTERACTIVETOKEN\n\nsim\n"

        with patch("httpx.post", side_effect=_fake_token_exchange_success):
            result = cli_runner.invoke(app, ["auth", "set"], input=stdin)

        assert result.exit_code == 0, result.output
        assert creds_path.exists()
        payload = json.loads(creds_path.read_text())["payload"]
        assert payload["client_id"] == "INTERACTIVEID"

    def test_set_interactive_masked_prompts_not_echoed(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Secret prompts should use hide_input — the entered value must NOT appear in output."""
        stdin = "MYSECRETCLIENTID\nMYSECRETSECRET\nMYSECRETTOKEN\n\nsim\n"

        with patch("httpx.post", side_effect=_fake_token_exchange_success):
            result = cli_runner.invoke(app, ["auth", "set"], input=stdin)

        # The secret values should not appear verbatim in the output
        assert "MYSECRETCLIENTID" not in result.output
        assert "MYSECREETSECRET" not in result.output
        assert "MYSECRETTOKEN" not in result.output
