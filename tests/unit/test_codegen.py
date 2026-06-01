"""Tests for scripts/codegen.py — verifies the codegen pipeline.

Acceptance criteria exercised:
- codegen.py runs to completion and writes models.py with expected classes
- MANIFEST.txt is written with correct fields
- __init__.py has the DO NOT EDIT header
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATED_DIR = REPO_ROOT / "src" / "tradestation" / "_generated"
MODELS_FILE = GENERATED_DIR / "models.py"
OPERATIONS_FILE = GENERATED_DIR / "operations.py"
MANIFEST_FILE = GENERATED_DIR / "MANIFEST.txt"
INIT_FILE = GENERATED_DIR / "__init__.py"


# ---------------------------------------------------------------------------
# Tests: generated files exist
# ---------------------------------------------------------------------------


def test_models_file_exists() -> None:
    """models.py must exist and be non-empty after codegen."""
    assert MODELS_FILE.exists(), f"models.py not found at {MODELS_FILE}"
    assert MODELS_FILE.stat().st_size > 1000, "models.py is suspiciously small"


def test_operations_file_exists() -> None:
    """operations.py must exist and be non-empty."""
    assert OPERATIONS_FILE.exists(), f"operations.py not found at {OPERATIONS_FILE}"
    assert OPERATIONS_FILE.stat().st_size > 1000, "operations.py is suspiciously small"


def test_manifest_exists() -> None:
    """MANIFEST.txt must exist."""
    assert MANIFEST_FILE.exists(), f"MANIFEST.txt not found at {MANIFEST_FILE}"


def test_init_has_do_not_edit_header() -> None:
    """__init__.py must have the DO NOT EDIT header."""
    text = INIT_FILE.read_text(encoding="utf-8")
    assert "DO NOT EDIT" in text, "__init__.py missing 'DO NOT EDIT' header"
    assert "scripts/codegen.py" in text, "__init__.py missing codegen script reference"


# ---------------------------------------------------------------------------
# Tests: models.py content
# ---------------------------------------------------------------------------


def test_models_has_pydantic_imports() -> None:
    """models.py must import from pydantic."""
    text = MODELS_FILE.read_text(encoding="utf-8")
    assert "from pydantic" in text, "models.py does not import from pydantic"


def test_models_has_expected_classes() -> None:
    """models.py must contain generated classes from the swagger definitions."""
    text = MODELS_FILE.read_text(encoding="utf-8")
    # These class names come directly from the swagger definitions
    expected_classes = [
        "Error",
        "QuoteDefinitionItem",
        "SymbolDefinition",
        "AccountBalancesDefinitionItem",
        "AccountPositionsDefinitionItem",
        "AccountOrdersDefinitionItem",
        "OrderRequestDefinition",
        "OrderConfirmRequestDefinition",
        "OrderResponseDefinition",
        "ActivationTriggerDefinition",
    ]
    missing = [cls for cls in expected_classes if f"class {cls}" not in text]
    assert not missing, f"models.py missing expected classes: {missing}"


def test_models_class_count() -> None:
    """models.py must define at least 30 classes (BaseModel + RootModel + Enum)."""
    text = MODELS_FILE.read_text(encoding="utf-8")
    class_lines = re.findall(
        r"^class \w+\((?:BaseModel|RootModel|Enum|IntEnum|StrEnum)",
        text,
        re.MULTILINE,
    )
    assert len(class_lines) >= 30, f"Expected >= 30 classes, found {len(class_lines)}"


def test_models_has_enums() -> None:
    """models.py must contain at least one Enum class."""
    text = MODELS_FILE.read_text(encoding="utf-8")
    enum_classes = re.findall(r"^class \w+\(Enum\)", text, re.MULTILINE)
    assert len(enum_classes) >= 5, f"Expected >= 5 enums, found {len(enum_classes)}"


def test_models_importable() -> None:
    """The generated models module must be importable."""
    # Force reload to catch any import errors
    if "tradestation._generated.models" in sys.modules:
        del sys.modules["tradestation._generated.models"]
    module = importlib.import_module("tradestation._generated.models")
    assert module is not None
    # Must have more than 30 names (AC4)
    assert len(dir(module)) > 30, f"Expected > 30 names, got {len(dir(module))}"


# ---------------------------------------------------------------------------
# Tests: MANIFEST.txt content
# ---------------------------------------------------------------------------


def test_manifest_has_required_fields() -> None:
    """MANIFEST.txt must contain all required fields."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    required_fields = [
        "generated_at",
        "generator",
        "source",
        "source_sha",
        "source_sha256",
        "overlay",
        "operations",
        "models",
        "enums",
    ]
    missing = [f for f in required_fields if f not in text]
    assert not missing, f"MANIFEST.txt missing fields: {missing}"


def test_manifest_operations_count() -> None:
    """MANIFEST.txt operations count must be >= 20."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    match = re.search(r"^operations:\s+(\d+)", text, re.MULTILINE)
    assert match, "MANIFEST.txt missing 'operations:' line"
    count = int(match.group(1))
    assert count >= 20, f"Expected >= 20 operations, got {count}"


def test_manifest_models_count() -> None:
    """MANIFEST.txt models count must be >= 30."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    match = re.search(r"^models:\s+(\d+)", text, re.MULTILINE)
    assert match, "MANIFEST.txt missing 'models:' line"
    count = int(match.group(1))
    assert count >= 30, f"Expected >= 30 models, got {count}"


def test_manifest_enums_count() -> None:
    """MANIFEST.txt enums count must be > 0."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    match = re.search(r"^enums:\s+(\d+)", text, re.MULTILINE)
    assert match, "MANIFEST.txt missing 'enums:' line"
    count = int(match.group(1))
    assert count > 0, f"Expected > 0 enums, got {count}"


def test_manifest_sha256_format() -> None:
    """MANIFEST.txt source_sha256 must be a valid 64-char hex string."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    match = re.search(r"^source_sha256:\s+([0-9a-f]{64})", text, re.MULTILINE)
    assert match, "MANIFEST.txt missing or invalid source_sha256 line"


def test_manifest_generator_has_version() -> None:
    """MANIFEST.txt generator line must include a version number."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    match = re.search(r"^generator:\s+(.+)", text, re.MULTILINE)
    assert match, "MANIFEST.txt missing generator line"
    generator_str = match.group(1).strip()
    # Should contain a version-like string (e.g. "0.25.9")
    assert re.search(r"\d+\.\d+", generator_str), (
        f"Generator string missing version: {generator_str!r}"
    )


# ---------------------------------------------------------------------------
# Tests: all swagger operationIds covered in operations.py
# ---------------------------------------------------------------------------


def test_all_operation_ids_covered() -> None:
    """Every operationId in vendor/swagger.yaml must have a callable in operations.py.

    This is the coverage guarantee test from docs/09-codegen-strategy.md.
    Each swagger operationId must appear (as text) in operations.py —
    either as a function name or in a docstring.
    """
    swagger_file = REPO_ROOT / "vendor" / "swagger.yaml"
    assert swagger_file.exists(), "vendor/swagger.yaml not found"

    # Extract all operationIds from the swagger file
    swagger_text = swagger_file.read_text(encoding="utf-8")
    operation_ids = re.findall(r"^\s+operationId:\s+(\S+)", swagger_text, re.MULTILINE)
    assert operation_ids, "No operationIds found in swagger.yaml"

    # Each operationId must appear somewhere in operations.py
    ops_text = OPERATIONS_FILE.read_text(encoding="utf-8")
    missing = [op_id for op_id in operation_ids if op_id not in ops_text]
    assert not missing, (
        "The following swagger operationIds are NOT referenced in operations.py:\n"
        + "\n".join(f"  - {op_id}" for op_id in missing)
    )
