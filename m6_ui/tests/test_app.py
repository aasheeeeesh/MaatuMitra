"""Streamlit AppTest: the acceptance behaviours of the review app (MODE=mock)."""

from __future__ import annotations

import html as htmllib
import re

import pytest
from streamlit.testing.v1 import AppTest

from m6_ui import i18n
from m6_ui.tests.helpers import APP

T = 90  # seconds per script run (first run imports a lot on Windows)


def _texts(at) -> str:
    parts = [e.value for e in at.html]
    for group in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        parts += [str(e.value) for e in group]
    parts += [b.label for b in at.button]
    return "\n".join(parts)


def _start(
    record_id: str | None = None, page: str = "review", lang: str = "en", role: str = "physician"
):
    at = AppTest.from_file(str(APP), default_timeout=T)
    at.session_state["lang"] = lang
    if role:
        at.session_state["role"] = role
    if record_id:
        at.session_state["record_id"] = record_id
        at.session_state["page"] = page
    at.run()
    assert not at.exception, at.exception
    return at


def _click(at, key):
    at.button(key=key).click().run()
    assert not at.exception, at.exception
    return at


def _row_order(at):
    rows = []
    for e in at.html:
        m = re.search(r'data-row-path="([^"]+)" data-flagged="([01])"', e.value)
        if m:
            rows.append((m.group(1), m.group(2) == "1"))
    return rows


# --------------------------------------------------------------------------- screens 1-2


def test_role_picker_is_first_and_language_toggle_switches_every_label():
    at = AppTest.from_file(str(APP), default_timeout=T).run()
    assert not at.exception
    text = _texts(at)
    assert i18n.t("app.title", "kn") in text  # Kannada first
    assert at.button(key="role_asha").label == i18n.t("role.asha", "kn")
    _click(at, "lang_en")
    text = _texts(at)
    assert i18n.t("app.title", "en") in text
    assert i18n.t("app.title", "kn") not in text
    assert at.button(key="role_asha").label == i18n.t("role.asha", "en")
    _click(at, "lang_kn")
    assert at.button(key="role_asha").label == i18n.t("role.asha", "kn")


def test_full_flow_role_record_review():
    at = AppTest.from_file(str(APP), default_timeout=T)
    at.session_state["lang"] = "en"
    at.run()
    _click(at, "role_pharmacist")
    text = _texts(at)
    assert i18n.t("record.state_none", "en") in text
    assert i18n.t("record.mock_note", "en") in text
    assert at.audio_input(key="audio_rec") is not None
    at.selectbox(key="fixture_pick").set_value("rec-fx-pharm-003-asr").run()
    _click(at, "go_review")
    assert _row_order(at)[0] == ("/medications/0/dose_value", True)


# --------------------------------------------------------------------------- screen 3


def test_flagged_fields_are_rendered_first_with_colour_icon_and_label():
    at = _start("rec-fx-nurse-005")
    order = _row_order(at)
    assert order[0] == ("/symptoms/1", True)
    assert [f for _, f in order] == sorted([f for _, f in order], reverse=True)
    head = next(e.value for e in at.html if 'data-row-path="/symptoms/1"' in e.value)
    assert "row-flag" in head  # colour (CSS class)
    assert 'class="icon icon-flag"' in head  # icon
    assert i18n.t("badge.flag", "en") in head  # text label


def test_flag_reasons_are_visible_without_a_click_in_both_languages():
    at = _start("rec-fx-pharm-003-asr", lang="en")
    text = _texts(at)
    for cid in ("C4", "C7"):
        assert htmllib.escape(i18n.t(f"reason.{cid}", "kn")) in text
        assert htmllib.escape(i18n.t(f"reason.{cid}", "en")) in text
    assert htmllib.escape("critical token '50' has confidence 0.41") in text
    assert len(at.expander) == 0


def test_transcript_evidence_is_highlighted():
    at = _start("rec-fx-pharm-003-asr")
    tr = next(e.value for e in at.html if 'class="transcript"' in e.value)
    assert 'class="ev ev-flag"' in tr and 'class="ev"' in tr


def test_play_this_part_cuts_audio_or_says_no_timing():
    at = _start("rec-fx-pharm-003-asr")
    assert len(at.get("audio")) == 0
    _click(at, "play_medications-0-dose_value")
    assert len(at.get("audio")) == 1
    assert i18n.t("play.mock_note", "en") in _texts(at)

    at = _start("rec-fx-nurse-005")
    _click(at, "play_symptoms-1")
    assert len(at.get("audio")) == 0
    assert i18n.t("play.no_timing", "en") in _texts(at)


# --------------------------------------------------------------------------- screen 4


def test_approve_disabled_until_every_flag_is_individually_resolved():
    at = _start("rec-m6-xss")
    flagged = [p for p, f in _row_order(at) if f]
    assert flagged == ["/medications/0/dose_value", "/advice/0"]
    assert at.button(key="approve").disabled
    _click(at, "yes_medications-0-dose_value")
    assert at.button(key="approve").disabled, "one flag still open"
    assert i18n.t("approve.blocked", "en").format(n=1) in _texts(at)
    _click(at, "yes_advice-0")
    assert not at.button(key="approve").disabled
    _click(at, "undo_advice-0")
    assert at.button(key="approve").disabled


def test_server_refusal_is_shown_and_record_is_not_saved():
    # an edit that the re-run checker still flags: the server (mock gate) refuses the save
    at = _start("rec-fx-pharm-003-asr")
    _click(at, "no_medications-0-dose_value")
    at.number_input(key="in_medications-0-dose_value_dose_value").set_value(500.0)
    _click(at, "save_medications-0-dose_value")
    _click(at, "yes_medications-0-dose_value")
    assert not at.button(key="approve").disabled
    _click(at, "approve")
    text = _texts(at)
    assert i18n.t("gate.refused_title", "en") in text
    assert htmllib.escape(i18n.t("gate.code.refused_not_reverified", "en")) in text
    assert i18n.t("status.not_saved", "en") in text
    assert i18n.t("gate.saved", "en") not in text


def test_confirming_every_flag_one_by_one_then_approve_is_saved_by_the_server():
    # D-94: the physician's per-flag confirmation IS the approval; the server checks it
    at = _start("rec-fx-pharm-003-asr")
    _click(at, "yes_medications-0-dose_value")
    _click(at, "approve")
    assert i18n.t("gate.saved", "en") in _texts(at)


def test_forced_server_refusal_is_handled(monkeypatch):
    monkeypatch.setenv("M6_MOCK_GATE_REFUSE", "1")
    at = _start("rec-fx-asha-001")
    assert not at.button(key="approve").disabled  # nothing flagged, but still needs a human click
    assert i18n.t("gate.saved", "en") not in _texts(at)
    _click(at, "approve")
    text = _texts(at)
    assert i18n.t("gate.refused_title", "en") in text
    assert htmllib.escape(i18n.t("gate.code.refused_forced", "en")) in text


def test_clean_record_saves_only_after_click():
    at = _start("rec-fx-asha-001")
    assert i18n.t("gate.saved", "en") not in _texts(at)
    _click(at, "approve")
    assert i18n.t("gate.saved", "en") in _texts(at)


def test_edit_reruns_verifier_and_new_flag_must_be_resolved():
    at = _start("rec-fx-pharm-003-asr")
    _click(at, "no_medications-0-dose_value")
    at.number_input(key="in_medications-0-dose_value_dose_value").set_value(500.0)
    _click(at, "save_medications-0-dose_value")
    text = _texts(at)
    assert "500" in text
    assert htmllib.escape(i18n.t("reason.C2", "en")) in text
    assert at.button(key="approve").disabled, "new C2 flag after the edit is still open"
    _click(at, "yes_medications-0-dose_value")
    assert not at.button(key="approve").disabled
    _click(at, "approve")  # the stand-in still flags the edit: the server refuses
    assert htmllib.escape(i18n.t("gate.code.refused_not_reverified", "en")) in _texts(at)


# --------------------------------------------------------------------------- security


def test_xss_payload_in_transcript_and_fields_renders_inert():
    at = _start("rec-m6-xss")
    rendered = "\n".join(e.value for e in at.html if not e.value.lstrip().startswith("<style"))
    for bad in ("<script", "<img", "<b onmouseover", "<i>xss"):
        assert bad not in rendered, bad
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in rendered
    assert "&lt;img src=x onerror=alert(&#x27;reason&#x27;)&gt;" in rendered
    for md in at.markdown:
        assert "<script" not in md.value and "<img" not in md.value


# --------------------------------------------------------------------------- screens 5-6 + font page


def test_counselling_placeholder_and_ask_a_doctor_state():
    at = _start("rec-fx-asha-001", page="help")
    text = _texts(at)
    assert i18n.t("help.placeholder", "en") in text
    assert i18n.t("help.ask_doctor_title", "en") not in text
    _click(at, "help_not_sure")
    assert i18n.t("help.ask_doctor_title", "en") in _texts(at)


def test_counselling_card_shows_not_validated_status():
    at = _start("rec-fx-asha-001", page="help")
    _click(at, "card_card-hand-hygiene")
    text = _texts(at)
    assert i18n.t("help.card_status_machine", "en") in text
    assert htmllib.escape(i18n.t("help.not_clinician", "en")) in text


def test_failure_panel_lists_cases():
    at = _start("rec-fx-asha-001", page="fail")
    text = _texts(at)
    assert i18n.t("fail.intro", "en") in text
    assert "fail-row" in text


@pytest.mark.parametrize("lang", ["kn", "en"])
def test_font_test_page_lists_conjuncts(lang):
    at = _start("rec-fx-asha-001", page="font", lang=lang)
    text = _texts(at)
    assert "".join(map(chr, (0x0C95, 0x0CCD, 0x0CB7))) in text  # ka + virama + ssa
    assert "U+0CB8 U+0CCD U+0CA4 U+0CCD U+0CB0 U+0CC0" in text
