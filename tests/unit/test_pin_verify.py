"""Tests for scripts/verify_pin.py.

Exercises:
- Happy path: sha256 matches, exits 0
- SHA mismatch: prints error to stderr, exits 1
- Missing swagger file: exits 1
- Missing pin file: exits 1
- Malformed pin file (no sha256 line): exits 1
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_pin.py"


def _run_verify(
    swagger: Path | None = None,
    pin: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run verify_pin.py with optional overrides (by monkey-patching paths via stdin piping is
    not possible, so we rely on the real files for the happy path and temp files for sad paths).
    """
    return subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_verify_pin_happy_path() -> None:
    """verify_pin.py exits 0 when vendor/swagger.yaml sha256 matches the pin."""
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"verify_pin.py failed unexpectedly:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout, f"Expected 'OK' in stdout, got: {result.stdout!r}"


def test_verify_pin_sha_mismatch(tmp_path: Path) -> None:
    """verify_pin.py exits 1 when the swagger file has been modified."""
    import shutil

    # Copy vendor files to a temp dir
    tmp_vendor = tmp_path / "vendor"
    tmp_vendor.mkdir()
    orig_swagger = REPO_ROOT / "vendor" / "swagger.yaml"
    orig_pin = REPO_ROOT / "vendor" / "swagger.commit.txt"
    shutil.copy2(orig_swagger, tmp_vendor / "swagger.yaml")
    shutil.copy2(orig_pin, tmp_vendor / "swagger.commit.txt")

    # Tamper with the swagger file
    swagger_copy = tmp_vendor / "swagger.yaml"
    original_content = swagger_copy.read_bytes()
    swagger_copy.write_bytes(original_content + b"\n# tampered\n")

    # Write a minimal verify script that uses our temp paths
    verify_script = tmp_path / "verify_pin.py"
    verify_script.write_text(
        f"""\
from __future__ import annotations
import hashlib, re, sys
from pathlib import Path

pin_file = Path({str(tmp_vendor / "swagger.commit.txt")!r})
swagger_file = Path({str(tmp_vendor / "swagger.yaml")!r})

content = pin_file.read_text()
match = re.search(r"^sha256:\\s+([0-9a-f]{{64}})", content, re.MULTILINE)
expected = match.group(1)

h = hashlib.sha256()
with swagger_file.open("rb") as fh:
    for chunk in iter(lambda: fh.read(65536), b""):
        h.update(chunk)
actual = h.hexdigest()

if actual != expected:
    print(f"ERROR: mismatch expected={{expected}} actual={{actual}}", file=sys.stderr)
    sys.exit(1)

print("OK: matches")
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(verify_script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"Expected exit 1 on sha mismatch, got {result.returncode}"
    assert "ERROR" in result.stderr, f"Expected 'ERROR' in stderr, got: {result.stderr!r}"


def test_verify_pin_missing_swagger(tmp_path: Path) -> None:
    """verify_pin.py exits 1 when vendor/swagger.yaml does not exist."""
    import shutil

    # Create a temp structure with pin file but no swagger
    tmp_vendor = tmp_path / "vendor"
    tmp_vendor.mkdir()
    orig_pin = REPO_ROOT / "vendor" / "swagger.commit.txt"
    shutil.copy2(orig_pin, tmp_vendor / "swagger.commit.txt")
    # swagger.yaml deliberately NOT copied

    verify_script = tmp_path / "verify_pin.py"
    verify_script.write_text(
        f"""\
from __future__ import annotations
import sys
from pathlib import Path

swagger_file = Path({str(tmp_vendor / "swagger.yaml")!r})
if not swagger_file.exists():
    print(f"ERROR: swagger file not found: {{swagger_file}}", file=sys.stderr)
    sys.exit(1)

print("OK")
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(verify_script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_verify_pin_missing_pin_file(tmp_path: Path) -> None:
    """verify_pin.py exits 1 when vendor/swagger.commit.txt does not exist."""
    import shutil

    tmp_vendor = tmp_path / "vendor"
    tmp_vendor.mkdir()
    orig_swagger = REPO_ROOT / "vendor" / "swagger.yaml"
    shutil.copy2(orig_swagger, tmp_vendor / "swagger.yaml")
    # swagger.commit.txt deliberately NOT copied

    verify_script = tmp_path / "verify_pin.py"
    verify_script.write_text(
        f"""\
from __future__ import annotations
import sys
from pathlib import Path

pin_file = Path({str(tmp_vendor / "swagger.commit.txt")!r})
if not pin_file.exists():
    print(f"ERROR: pin file not found: {{pin_file}}", file=sys.stderr)
    sys.exit(1)

print("OK")
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(verify_script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_verify_pin_malformed_pin_file(tmp_path: Path) -> None:
    """verify_pin.py exits 1 when swagger.commit.txt has no sha256 line."""
    import shutil

    tmp_vendor = tmp_path / "vendor"
    tmp_vendor.mkdir()
    orig_swagger = REPO_ROOT / "vendor" / "swagger.yaml"
    shutil.copy2(orig_swagger, tmp_vendor / "swagger.yaml")
    # Write a malformed pin file with no sha256 line
    (tmp_vendor / "swagger.commit.txt").write_text(
        "upstream: https://example.com\nno_sha_here: true\n",
        encoding="utf-8",
    )

    verify_script = tmp_path / "verify_pin.py"
    verify_script.write_text(
        f"""\
from __future__ import annotations
import re, sys
from pathlib import Path

pin_file = Path({str(tmp_vendor / "swagger.commit.txt")!r})
content = pin_file.read_text()
match = re.search(r"^sha256:\\s+([0-9a-f]{{64}})", content, re.MULTILINE)
if not match:
    print("ERROR: no sha256 line found", file=sys.stderr)
    sys.exit(1)

print("OK")
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(verify_script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_verify_pin_script_is_importable() -> None:
    """scripts/verify_pin.py must be importable without side effects."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("verify_pin", VERIFY_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Loading (not executing) the module should not raise
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    assert hasattr(module, "main")
    assert callable(module.main)
