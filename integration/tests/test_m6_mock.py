"""m6 in mock mode (Streamlit AppTest) renders a record without raising."""

from __future__ import annotations

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def test_review_screen_shows_a_fixture_record_in_mock_mode(monkeypatch):
    from m6_ui.tests.helpers import APP

    monkeypatch.setenv("MODE", "mock")
    monkeypatch.delenv("API_URL", raising=False)
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.session_state["lang"] = "en"
    at.session_state["role"] = "physician"
    at.session_state["record_id"] = "rec-fx-phys-004"
    at.session_state["page"] = "review"
    at.run()
    assert not at.exception, at.exception
    text = "\n".join([e.value for e in at.html] + [str(e.value) for e in at.markdown])
    assert text.strip(), "review screen rendered nothing"
