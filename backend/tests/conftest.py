"""Test-wide fixtures.

GIPHY is real, best-effort content - right for the live app, wrong for
tests. Without this, the suite would hit the real GIPHY API whenever a real
key happens to be configured in .env, making reel-content assertions depend
on network access and an external account instead of being deterministic.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def no_giphy(monkeypatch):
    monkeypatch.setattr(config, "GIPHY_API_KEY", "")
