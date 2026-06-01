"""Verify that vendor/swagger.yaml matches the sha256 recorded in vendor/swagger.commit.txt.

Run by CI on every PR (via .github/workflows/verify-pin.yml) and locally via
``make vendor`` or directly::

    python scripts/verify_pin.py

Exit 0 if the sha256 matches; exit 1 (with a clear error) if it does not.

See docs/09-codegen-strategy.md §"CI integration" for the full design.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root (parent of this script's directory)."""
    return Path(__file__).resolve().parent.parent


def _read_expected_sha256(pin_file: Path) -> str:
    """Parse the sha256 value from vendor/swagger.commit.txt.

    The pin file contains a line like::

        sha256:          061b6b092458c906fbd7413abf79b07cbbe484b9c3de2142e5d8b134479b03b4

    Returns:
        The 64-character hex sha256 string.

    Raises:
        SystemExit: If the pin file is missing or the sha256 line is absent.
    """
    if not pin_file.exists():
        print(f"ERROR: pin file not found: {pin_file}", file=sys.stderr)
        sys.exit(1)

    content = pin_file.read_text(encoding="utf-8")
    match = re.search(r"^sha256:\s+([0-9a-f]{64})", content, re.MULTILINE)
    if not match:
        print(
            f"ERROR: no 'sha256: <hex>' line found in {pin_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    return match.group(1)


def _compute_sha256(file: Path) -> str:
    """Compute the sha256 hex digest of *file*."""
    h = hashlib.sha256()
    with file.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    """Entry point — verify pin and exit 0/1."""
    root = _repo_root()
    pin_file = root / "vendor" / "swagger.commit.txt"
    swagger_file = root / "vendor" / "swagger.yaml"

    if not swagger_file.exists():
        print(f"ERROR: swagger file not found: {swagger_file}", file=sys.stderr)
        sys.exit(1)

    expected = _read_expected_sha256(pin_file)
    actual = _compute_sha256(swagger_file)

    if actual != expected:
        print(
            "ERROR: vendor/swagger.yaml sha256 mismatch!\n"
            f"  expected : {expected}\n"
            f"  actual   : {actual}\n\n"
            "If you intentionally updated the spec, re-run `make vendor` to "
            "update vendor/swagger.commit.txt.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"OK: vendor/swagger.yaml sha256 matches pin ({actual[:12]}...)")


if __name__ == "__main__":
    main()
