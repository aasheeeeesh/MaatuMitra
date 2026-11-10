"""m6_ui test setup: MODE=mock is forced for every test."""

import pytest


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    monkeypatch.setenv("MODE", "mock")
    monkeypatch.delenv("M6_MOCK_GATE_REFUSE", raising=False)
    monkeypatch.delenv("API_URL", raising=False)
