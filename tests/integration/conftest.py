"""Conftest for integration tests — loads .env lazily via a fixture.

Loading .env at module/collection time would set TS_CLIENT_ID globally, which
causes Typer's envvar= options to override test-supplied values in non-integration
tests.  Instead, we load it only inside a pytest fixture that live tests request.
"""

from __future__ import annotations

import pathlib

import pytest


@pytest.fixture(scope="session", autouse=False)
def _load_dotenv_for_live_tests() -> None:
    """Load .env once per session for integration tests that need live credentials."""
    try:
        from dotenv import load_dotenv as _load_dotenv

        _load_dotenv(pathlib.Path(__file__).parent.parent.parent / ".env", override=False)
    except ImportError:
        pass
