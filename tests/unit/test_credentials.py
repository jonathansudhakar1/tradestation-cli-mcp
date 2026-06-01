"""Unit tests for tradestation.credentials.

Tests:
    - round-trip encrypt/decrypt (keyring path)
    - round-trip encrypt/decrypt (passphrase path)
    - atomic rotation (save/load with token update)
    - filelock contention (concurrent saves)
    - from_env() loader
    - profile loader
    - default environment is SIM
    - plaintext scheme
    - missing file → NoCredentialsError
    - corrupt JSON → AuthError
    - wrong passphrase → AuthError
    - TS_CREDENTIALS env var override
"""

from __future__ import annotations

import json
import pathlib
import threading
from unittest.mock import MagicMock, patch

import pytest

from tradestation.credentials import (
    Credentials,
    _default_credentials_path,
    _derive_key_pbkdf2,
    from_env,
    load,
    save,
)
from tradestation.enums import Environment
from tradestation.errors import AuthError, NoCredentialsError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creds(**kwargs: object) -> Credentials:
    defaults = {
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "rtoken",
    }
    defaults.update(kwargs)  # type: ignore[arg-type]
    return Credentials(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Default environment
# ---------------------------------------------------------------------------


class TestDefaultEnvironment:
    def test_default_is_sim(self) -> None:
        c = _make_creds()
        assert c.environment == Environment.SIM

    def test_explicit_live(self) -> None:
        c = _make_creds(environment=Environment.LIVE)
        assert c.environment == Environment.LIVE
        assert c.base_url == "https://api.tradestation.com/v3"

    def test_explicit_sim(self) -> None:
        c = _make_creds(environment=Environment.SIM)
        assert c.environment == Environment.SIM
        assert c.base_url == "https://sim-api.tradestation.com/v3"

    def test_frozen(self) -> None:
        c = _make_creds()
        with pytest.raises((AttributeError, TypeError)):
            c.client_id = "oops"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Keyring round-trip
# ---------------------------------------------------------------------------


class TestKeyringRoundTrip:
    def test_save_and_load_keyring(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        monkeypatch.setenv("TS_CREDENTIALS", str(creds_path))

        original = _make_creds(access_token="tok123")
        save(original, creds_path)

        # File should exist with 0600 perms
        assert creds_path.exists()
        perms = oct(creds_path.stat().st_mode)[-3:]
        assert perms == "600"

        loaded = load(creds_path)
        assert loaded.client_id == original.client_id
        assert loaded.client_secret == original.client_secret
        assert loaded.refresh_token == original.refresh_token
        assert loaded.access_token == original.access_token
        assert loaded.environment == original.environment

    def test_keyring_key_stored(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        save(_make_creds(), creds_path)
        # Verify keyring.set_password was called with our service/account
        fake_keyring.set_password.assert_called()
        call_args = fake_keyring.set_password.call_args
        assert call_args[0][0] == "tscli"
        assert call_args[0][1] == "credentials-key-v1"

    def test_envelope_structure(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        save(_make_creds(), creds_path)

        raw = json.loads(creds_path.read_text())
        assert raw["version"] == 1
        assert raw["scheme"] == "fernet-v1"
        assert "ciphertext_b64" in raw
        assert "kdf" in raw


# ---------------------------------------------------------------------------
# Passphrase round-trip
# ---------------------------------------------------------------------------


class TestPassphraseRoundTrip:
    def test_save_and_load_passphrase(
        self,
        tmp_credentials_dir: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TSCLI_PASSPHRASE", "secure-pass-xyz-123")
        # Make keyring unavailable
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.side_effect = Exception("no keyring")

        creds_path = tmp_credentials_dir / "credentials"
        original = _make_creds()

        with patch("tradestation.credentials.keyring", mock_keyring):
            save(original, creds_path)
            loaded = load(creds_path)

        assert loaded.client_id == original.client_id
        assert loaded.refresh_token == original.refresh_token

    def test_wrong_passphrase_raises(
        self,
        tmp_credentials_dir: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TSCLI_PASSPHRASE", "correct-pass")
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.side_effect = Exception("no keyring")

        creds_path = tmp_credentials_dir / "credentials"

        with patch("tradestation.credentials.keyring", mock_keyring):
            save(_make_creds(), creds_path)

        # Now tamper with passphrase
        monkeypatch.setenv("TSCLI_PASSPHRASE", "wrong-pass")

        with patch("tradestation.credentials.keyring", mock_keyring), pytest.raises(AuthError):
            load(creds_path)

    def test_pbkdf2_key_derivation_deterministic(self) -> None:
        passphrase = "test-passphrase"
        salt = b"a" * 24
        key1 = _derive_key_pbkdf2(passphrase, salt)
        key2 = _derive_key_pbkdf2(passphrase, salt)
        assert key1 == key2

    def test_pbkdf2_different_salts(self) -> None:
        passphrase = "test-passphrase"
        key1 = _derive_key_pbkdf2(passphrase, b"a" * 24)
        key2 = _derive_key_pbkdf2(passphrase, b"b" * 24)
        assert key1 != key2


# ---------------------------------------------------------------------------
# Plaintext scheme
# ---------------------------------------------------------------------------


class TestPlaintextScheme:
    def test_save_plaintext(
        self,
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        original = _make_creds()
        save(original, creds_path, encrypt=False)

        raw = json.loads(creds_path.read_text())
        assert raw["scheme"] == "plaintext"
        assert "payload" in raw
        assert raw["payload"]["client_id"] == "cid"

    def test_load_plaintext(
        self,
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        original = _make_creds()
        save(original, creds_path, encrypt=False)
        loaded = load(creds_path)
        assert loaded.client_id == original.client_id


# ---------------------------------------------------------------------------
# Atomic rotation
# ---------------------------------------------------------------------------


class TestAtomicRotation:
    def test_save_overwrites_atomically(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"

        creds_v1 = _make_creds(refresh_token="old-token")
        save(creds_v1, creds_path)

        creds_v2 = _make_creds(refresh_token="new-token")
        save(creds_v2, creds_path)

        loaded = load(creds_path)
        assert loaded.refresh_token == "new-token"

    def test_no_tmp_files_left_behind(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        save(_make_creds(), creds_path)

        tmp_files = list(tmp_credentials_dir.glob(".tmp_creds_*"))
        assert tmp_files == [], f"Temp files remain: {tmp_files}"


# ---------------------------------------------------------------------------
# Filelock contention
# ---------------------------------------------------------------------------


class TestFilelockContention:
    def test_concurrent_saves_consistent(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        errors: list[Exception] = []

        def _write(token: str) -> None:
            try:
                save(_make_creds(refresh_token=token), creds_path)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_write, args=(f"token-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # File should be valid JSON and loadable
        loaded = load(creds_path)
        assert loaded.refresh_token.startswith("token-")


# ---------------------------------------------------------------------------
# Missing / corrupt file
# ---------------------------------------------------------------------------


class TestFileErrors:
    def test_missing_file_raises_no_credentials(
        self,
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        creds_path = tmp_credentials_dir / "nonexistent"
        with pytest.raises(NoCredentialsError):
            load(creds_path)

    def test_corrupt_json_raises_auth_error(
        self,
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        creds_path.write_text("NOT JSON!!!")
        with pytest.raises(AuthError):
            load(creds_path)

    def test_unknown_scheme_raises_auth_error(
        self,
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        envelope = {"version": 1, "scheme": "ultra-v9"}
        creds_path.write_text(json.dumps(envelope))
        with pytest.raises(AuthError):
            load(creds_path)


# ---------------------------------------------------------------------------
# from_env() loader
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_basic_from_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        monkeypatch.setenv("TS_CLIENT_ID", "env-cid")
        monkeypatch.setenv("TS_CLIENT_SECRET", "env-csec")
        monkeypatch.setenv("TS_REFRESH_TOKEN", "env-rtoken")

        c = from_env()
        assert c.client_id == "env-cid"
        assert c.client_secret == "env-csec"
        assert c.refresh_token == "env-rtoken"
        assert c.environment == Environment.SIM  # default

    def test_from_env_live(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        monkeypatch.setenv("TS_CLIENT_ID", "env-cid")
        monkeypatch.setenv("TS_REFRESH_TOKEN", "env-rtoken")
        monkeypatch.setenv("TS_ENV", "live")

        c = from_env()
        assert c.environment == Environment.LIVE

    def test_from_env_custom_scope(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        monkeypatch.setenv("TS_CLIENT_ID", "env-cid")
        monkeypatch.setenv("TS_REFRESH_TOKEN", "env-rtoken")
        monkeypatch.setenv("TS_SCOPE", "openid MarketData")

        c = from_env()
        assert c.scope == "openid MarketData"

    def test_missing_client_id_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        with pytest.raises(NoCredentialsError):
            from_env()

    def test_missing_refresh_token_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        monkeypatch.setenv("TS_CLIENT_ID", "cid")
        with pytest.raises(NoCredentialsError):
            from_env()

    def test_unknown_env_defaults_sim(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        monkeypatch.setenv("TS_CLIENT_ID", "cid")
        monkeypatch.setenv("TS_REFRESH_TOKEN", "rtoken")
        monkeypatch.setenv("TS_ENV", "bogus")
        c = from_env()
        assert c.environment == Environment.SIM

    def test_no_client_secret_is_ok(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_ts_env: None,
    ) -> None:
        monkeypatch.setenv("TS_CLIENT_ID", "cid")
        monkeypatch.setenv("TS_REFRESH_TOKEN", "rtoken")
        c = from_env()
        assert c.client_secret == ""


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------


class TestProfileLoader:
    def test_profile_creates_under_profiles_dir(
        self,
        tmp_path: pathlib.Path,
        fake_keyring: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        creds = _make_creds()
        save(creds, profile="paper")

        profile_path = tmp_path / ".tscli" / "profiles" / "paper" / "credentials"
        assert profile_path.exists()

    def test_load_by_profile(
        self,
        tmp_path: pathlib.Path,
        fake_keyring: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        original = _make_creds(client_id="profile-cid")
        save(original, profile="staging")

        loaded = load(profile="staging")
        assert loaded.client_id == "profile-cid"


# ---------------------------------------------------------------------------
# TS_CREDENTIALS env var
# ---------------------------------------------------------------------------


class TestCredentialsEnvVar:
    def test_ts_credentials_override(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        custom_path = tmp_credentials_dir / "custom_creds"
        monkeypatch.setenv("TS_CREDENTIALS", str(custom_path))

        original = _make_creds(client_id="custom-env-path")
        save(original)  # uses TS_CREDENTIALS
        loaded = load()  # uses TS_CREDENTIALS
        assert loaded.client_id == "custom-env-path"

    def test_default_path_respects_ts_credentials(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        custom = str(tmp_path / "my_creds_file")
        monkeypatch.setenv("TS_CREDENTIALS", custom)
        assert str(_default_credentials_path()) == custom


# ---------------------------------------------------------------------------
# Plaintext corrupt payload
# ---------------------------------------------------------------------------


class TestPlaintextCorrupt:
    def test_plaintext_missing_payload_raises(
        self,
        tmp_credentials_dir: pathlib.Path,
    ) -> None:
        creds_path = tmp_credentials_dir / "credentials"
        envelope = {"version": 1, "scheme": "plaintext", "payload": "not-a-dict"}
        creds_path.write_text(json.dumps(envelope))
        with pytest.raises(AuthError, match="payload"):
            load(creds_path)


# ---------------------------------------------------------------------------
# Keyring decrypt errors
# ---------------------------------------------------------------------------


class TestKeyringDecryptErrors:
    def test_keyring_returns_none_on_load_raises(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        """If keyring returns no key on load, should raise AuthError."""
        creds_path = tmp_credentials_dir / "credentials"
        # Save with keyring
        save(_make_creds(), creds_path)

        # Now make keyring return None for the key by clearing side_effect and setting return_value
        fake_keyring.get_password.side_effect = None
        fake_keyring.get_password.return_value = None

        with pytest.raises(AuthError):
            load(creds_path)

    def test_no_passphrase_no_keyring_raises_auth_error(
        self,
        tmp_credentials_dir: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When neither keyring nor passphrase is available, AuthError is raised."""
        # Remove passphrase env var
        monkeypatch.delenv("TSCLI_PASSPHRASE", raising=False)

        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.side_effect = Exception("no keyring")

        from tradestation.credentials import _encrypt_payload

        with patch("tradestation.credentials.keyring", mock_keyring), pytest.raises(AuthError):
            _encrypt_payload({"test": "data"}, use_keyring=False)


# ---------------------------------------------------------------------------
# credentials.replace()
# ---------------------------------------------------------------------------


class TestCredentialsReplace:
    def test_replace_returns_new_instance(self) -> None:
        c = _make_creds(access_token="old-tok")
        c2 = c.replace(access_token="new-tok")
        assert c2.access_token == "new-tok"
        assert c.access_token == "old-tok"  # original unchanged

    def test_replace_preserves_other_fields(self) -> None:
        c = _make_creds()
        c2 = c.replace(access_token="tok")
        assert c2.client_id == c.client_id
        assert c2.refresh_token == c.refresh_token


# ---------------------------------------------------------------------------
# load_credentials / save_credentials (legacy aliases)
# ---------------------------------------------------------------------------


class TestLegacyAliases:
    def test_load_credentials_alias(
        self,
        tmp_credentials_dir: pathlib.Path,
        fake_keyring: MagicMock,
    ) -> None:
        from tradestation.credentials import load_credentials, save_credentials

        creds_path = tmp_credentials_dir / "credentials"
        creds = _make_creds(client_id="alias-test")
        save_credentials(creds, creds_path)
        loaded = load_credentials(creds_path)
        assert loaded.client_id == "alias-test"
