"""Tests for the safety module: tokens, expiry, notional cap, audit log."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


class TestTokenGeneration:
    def test_generate_token_returns_string(self) -> None:
        from tradestation.mcp.safety import generate_token

        token = generate_token("abc123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_success(self) -> None:
        from tradestation.mcp.safety import generate_token, verify_token

        payload_hash = "deadbeef" * 8
        token = generate_token(payload_hash)
        assert verify_token(token, payload_hash) is True

    def test_verify_token_single_use(self) -> None:
        """Token can only be used once."""
        from tradestation.mcp.safety import generate_token, verify_token

        payload_hash = "cafebabe" * 8
        token = generate_token(payload_hash)
        assert verify_token(token, payload_hash) is True
        # Second attempt must fail
        assert verify_token(token, payload_hash) is False

    def test_verify_token_wrong_payload_fails(self) -> None:
        """Token bound to hash A is rejected for hash B."""
        from tradestation.mcp.safety import generate_token, verify_token

        token = generate_token("hash_a" * 4)
        assert verify_token(token, "hash_b" * 4) is False

    def test_verify_token_nonexistent_fails(self) -> None:
        from tradestation.mcp.safety import verify_token

        assert verify_token("totally-fake-token", "somehash") is False

    def test_token_expiry(self) -> None:
        """Token is rejected after TOKEN_TTL_SECONDS have elapsed."""
        from tradestation.mcp.safety import (
            TOKEN_TTL_SECONDS,
            generate_token,
            verify_token,
        )

        payload_hash = "expiring" * 8
        token = generate_token(payload_hash)

        # Advance real time past expiry by monkeypatching time.monotonic
        import tradestation.mcp.safety as safety_mod

        original = time.monotonic

        def fast_forward() -> float:
            return original() + TOKEN_TTL_SECONDS + 1

        safety_mod.time = type("t", (), {"monotonic": staticmethod(fast_forward)})()  # type: ignore[attr-defined]
        try:
            assert verify_token(token, payload_hash) is False
        finally:
            safety_mod.time = time  # type: ignore[attr-defined]

    def test_hash_payload_is_deterministic(self) -> None:
        """Same payload always yields the same hash."""
        from tradestation.mcp.safety import hash_payload

        payload = {"Symbol": "AAPL", "Quantity": 100, "AccountID": "111"}
        assert hash_payload(payload) == hash_payload(payload)

    def test_hash_payload_different_for_different_payloads(self) -> None:
        from tradestation.mcp.safety import hash_payload

        a = {"Symbol": "AAPL", "Quantity": 100}
        b = {"Symbol": "AAPL", "Quantity": 200}
        assert hash_payload(a) != hash_payload(b)


class TestNotionalCap:
    def test_within_cap_passes(self) -> None:
        from tradestation.mcp.safety import assert_notional_within_cap

        preview = {"EstimatedCost": "500.00"}
        assert_notional_within_cap(preview, 10000.0)  # Should not raise

    def test_exceeds_cap_raises(self) -> None:
        from tradestation.mcp.safety import assert_notional_within_cap

        preview = {"EstimatedCost": "60000.00"}
        with pytest.raises(ValueError, match="cap"):
            assert_notional_within_cap(preview, 50000.0)

    def test_negative_cost_uses_abs_value(self) -> None:
        from tradestation.mcp.safety import assert_notional_within_cap

        preview = {"EstimatedCost": "-60000.00"}
        with pytest.raises(ValueError, match="cap"):
            assert_notional_within_cap(preview, 50000.0)

    def test_missing_cost_passes(self) -> None:
        """No cost field — check is skipped (conservative)."""
        from tradestation.mcp.safety import assert_notional_within_cap

        preview: dict[str, str] = {}
        assert_notional_within_cap(preview, 100.0)  # Should not raise

    def test_camelcase_field_recognised(self) -> None:
        from tradestation.mcp.safety import assert_notional_within_cap

        preview = {"estimatedCost": "200.00"}
        assert_notional_within_cap(preview, 1000.0)  # Should not raise


class TestSymbolAllowlist:
    def test_allowed_symbol_passes(self) -> None:
        from tradestation.mcp.safety import assert_symbol_allowed

        assert_symbol_allowed("AAPL", ["AAPL", "MSFT"])

    def test_blocked_symbol_raises(self) -> None:
        from tradestation.mcp.safety import assert_symbol_allowed

        with pytest.raises(ValueError, match="not in the allowed-symbols list"):
            assert_symbol_allowed("TSLA", ["AAPL", "MSFT"])

    def test_empty_allowlist_permits_all(self) -> None:
        from tradestation.mcp.safety import assert_symbol_allowed

        assert_symbol_allowed("ANYTHING", [])  # Should not raise

    def test_case_insensitive_match(self) -> None:
        from tradestation.mcp.safety import assert_symbol_allowed

        assert_symbol_allowed("aapl", ["AAPL"])  # Should not raise


class TestAuditLog:
    def test_write_audit_log_creates_jsonl(self, tmp_path: Path) -> None:
        """write_audit_log writes a valid JSON line to the log file."""
        from pathlib import Path as _Path

        import tradestation.mcp.safety as safety_mod

        # Patch _audit_log_path to use tmp_path
        original_fn = safety_mod._audit_log_path

        def patched_path() -> _Path:
            return tmp_path / "mcp-audit.log"

        safety_mod._audit_log_path = patched_path  # type: ignore[attr-defined]
        try:
            from tradestation.mcp.safety import write_audit_log

            write_audit_log(
                tool="order_place",
                account="11111111",
                payload={"Symbol": "AAPL"},
                preview_hash="abc123",
                decision="confirm",
                result="success",
            )

            log_file = tmp_path / "mcp-audit.log"
            assert log_file.exists()
            lines = log_file.read_text().strip().split("\n")
            assert len(lines) == 1

            entry = json.loads(lines[0])
            assert entry["tool"] == "order_place"
            assert entry["account"] == "11111111"
            assert entry["decision"] == "confirm"
            assert entry["result"] == "success"
            assert "timestamp" in entry
        finally:
            safety_mod._audit_log_path = original_fn  # type: ignore[attr-defined]

    def test_write_audit_log_appends_multiple_lines(self, tmp_path: Path) -> None:
        """Multiple write_audit_log calls append multiple JSONL lines."""
        from pathlib import Path as _Path

        import tradestation.mcp.safety as safety_mod

        original_fn = safety_mod._audit_log_path

        def patched_path() -> _Path:
            return tmp_path / "mcp-audit.log"

        safety_mod._audit_log_path = patched_path  # type: ignore[attr-defined]
        try:
            from tradestation.mcp.safety import write_audit_log

            for decision in ("preview", "confirm"):
                write_audit_log(
                    tool="order_place",
                    account="11111111",
                    payload={"Symbol": "AAPL"},
                    preview_hash="hash1",
                    decision=decision,
                    result="ok",
                )

            lines = (tmp_path / "mcp-audit.log").read_text().strip().split("\n")
            assert len(lines) == 2
            assert json.loads(lines[0])["decision"] == "preview"
            assert json.loads(lines[1])["decision"] == "confirm"
        finally:
            safety_mod._audit_log_path = original_fn  # type: ignore[attr-defined]
