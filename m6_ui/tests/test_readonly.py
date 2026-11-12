"""A saved record is reopened read-only from the server's stored verdict (never re-verified)."""

from __future__ import annotations

import pytest

from m6_ui import i18n
from m6_ui.tests import fake_m5 as fm
from m6_ui.tests.helpers import M6, load_json
from m6_ui.tests.test_security import _click, _live, _login, _mock, _open_record, _texts

NEW_KEYS = ("review.saved_readonly", "review.resolutions_title", "review.no_stored_verdict")


@pytest.mark.parametrize("lang", ["kn", "en"])
def test_new_keys_exist_in_both_languages(lang):
    doc = load_json(M6 / "i18n" / f"{lang}.json")
    for k in NEW_KEYS:
        assert k in doc and doc[k].strip()


def _save_once(monkeypatch):
    m5 = fm.FakeM5()
    at, _, _ = _live(monkeypatch, m5)
    _login(at, fm.PHYS)
    _open_record(at)
    _click(at, "yes_medications-0-dose_value")
    _click(at, "approve")
    return m5


def _reopen(monkeypatch, m5, user):
    at, _, _ = _live(monkeypatch, m5)
    _login(at, user)
    n = len(m5.calls)
    _open_record(at)
    return at, m5.paths()[n:]


def test_live_physician_reopens_saved_record_read_only_with_resolutions(monkeypatch):
    m5 = _save_once(monkeypatch)
    at, calls = _reopen(monkeypatch, m5, fm.PHYS)
    text = _texts(at)
    assert i18n.t("review.saved_readonly", "en") in text
    assert i18n.t("review.saved_readonly", "kn") in text  # both languages, always
    assert i18n.t("review.resolutions_title", "en") in text
    assert not any(c.endswith("/verify") for c in calls)
    assert f"GET /records/{fm.RECORD_ID}/review" in calls
    keys = {b.key for b in at.button}
    assert not [k for k in keys if k.startswith(("yes_", "no_", "undo_", "save_"))]
    assert at.button(key="approve").disabled


def test_live_asha_sees_the_banner_but_not_the_resolutions(monkeypatch):
    m5 = _save_once(monkeypatch)
    at, _ = _reopen(monkeypatch, m5, fm.ASHA1)
    text = _texts(at)
    assert i18n.t("review.saved_readonly", "en") in text
    assert i18n.t("review.resolutions_title", "en") not in text
    assert at.button(key="approve").disabled


def test_mock_saved_record_reloads_read_only_and_does_not_verify_again():
    at = _mock("rec-fx-asha-001")
    _click(at, "approve")
    g = at.session_state["gate"]
    before = len(g._verdicts)
    at.session_state["work"] = {}  # as after a page reload: the working copy is gone
    at.run()
    assert not at.exception, at.exception
    text = _texts(at)
    assert i18n.t("review.saved_readonly", "en") in text
    assert len(g._verdicts) == before  # no new verdict was made for a saved record
    assert at.button(key="approve").disabled
    assert not [b for b in at.button if b.key.startswith(("yes_", "no_"))]
