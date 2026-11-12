"""D-123 (F1-F8) and D-94 save flow, as Streamlit AppTest. Live mode runs against fake_m5."""

from __future__ import annotations

import html as htmllib

import pytest
from streamlit.testing.v1 import AppTest

from m6_ui import gate, i18n
from m6_ui.tests import fake_m5 as fm
from m6_ui.tests.helpers import APP, M6

T = 90
BIDI = chr(0x202E)


def _texts(at) -> str:
    parts = [e.value for e in at.html]
    for group in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        parts += [str(e.value) for e in group]
    parts += [b.label for b in at.button]
    return "\n".join(parts)


def _live(monkeypatch, m5=None, lang="en"):
    monkeypatch.setenv("MODE", "live")
    monkeypatch.setenv("API_URL", "http://127.0.0.1:8000")
    m5 = m5 or fm.FakeM5()
    g = gate.HttpGate("http://127.0.0.1:8000", client=m5.client())
    at = AppTest.from_file(str(APP), default_timeout=T)
    at.session_state["lang"] = lang
    at.session_state["gate"] = g
    at.run()
    assert not at.exception, at.exception
    return at, m5, g


def _login(at, user, pw=fm.PASSWORD):
    at.text_input(key="login_user").set_value(user)
    at.text_input(key="login_password").set_value(pw)
    at.button(key="login_submit").click().run()
    assert not at.exception, at.exception


def _open_record(at, rid=fm.RECORD_ID):
    at.text_input(key="live_record_id").set_value(rid)
    at.button(key="go_review").click().run()
    assert not at.exception, at.exception


def _click(at, key):
    at.button(key=key).click().run()
    assert not at.exception, at.exception


def _mock(record_id, role="physician", lang="en", page="review"):
    at = AppTest.from_file(str(APP), default_timeout=T)
    at.session_state["lang"] = lang
    at.session_state["role"] = role
    at.session_state["record_id"] = record_id
    at.session_state["page"] = page
    at.run()
    assert not at.exception, at.exception
    return at


# ------------------------------------------------------------------ F1: per-person login


def test_f1_live_shows_a_login_and_no_role_buttons(monkeypatch):
    at, _, _ = _live(monkeypatch)
    keys = {b.key for b in at.button}
    assert "login_submit" in keys and not any(k.startswith("role_") for k in keys)
    assert i18n.t("login.title", "en") in _texts(at)


def test_f1_wrong_password_stays_on_login(monkeypatch):
    at, _, g = _live(monkeypatch)
    _login(at, fm.PHYS, "nope")
    assert not g.logged_in
    assert htmllib.escape(i18n.t("gate.code.refused_auth", "en")) in _texts(at)


def test_f1_role_comes_from_the_token_even_if_the_page_state_is_forged(monkeypatch):
    at, _, g = _live(monkeypatch)
    _login(at, fm.ASHA1)
    assert g.role == "asha"
    at.session_state["role"] = "physician"  # forged state
    at.session_state["gate"] = g
    _open_record(at)
    assert at.button(key="approve").disabled
    assert i18n.t("approve.physician_only", "en") in _texts(at)
    assert i18n.t("role.asha", "en") in _texts(at)


def test_f1_two_browser_sessions_two_logins(monkeypatch):
    m5 = fm.FakeM5()
    a, _, ga = _live(monkeypatch, m5)
    b, _, gb = _live(monkeypatch, m5)
    _login(a, fm.ASHA1)
    _login(b, fm.PHYS)
    assert (ga.role, gb.role) == ("asha", "physician")
    assert len(set(m5.tokens)) == 2


def test_f1_asha_sees_only_her_own_patients_from_the_server(monkeypatch):
    at, _, _ = _live(monkeypatch)
    _login(at, fm.ASHA1)
    text = _texts(at)
    assert "Patient-Own-A1" in text and "Patient-Other-A2" not in text


def test_f1_mock_roles_see_only_their_own_records_and_only_a_doctor_approves():
    at = _mock("rec-fx-asha-001", role="asha", page="record")
    opts = list(at.selectbox(key="fixture_pick").options)
    assert opts and "rec-fx-pharm-003-asr" not in opts and "rec-fx-phys-004" not in opts
    at = _mock("rec-fx-pharm-003-asr", role="pharmacist")
    assert at.button(key="approve").disabled
    assert i18n.t("approve.physician_only", "en") in _texts(at)
    at = _mock("rec-fx-phys-004", role="asha")  # a record outside her list
    assert i18n.t("review.no_record", "en") in _texts(at)
    assert not [b for b in at.button if b.key == "approve"]


# ------------------------------------------------------------------ F2 + F3 + D-94: live save


def test_f2_f3_live_record_is_loaded_from_m5_and_saved_by_the_same_id_without_approve(
    monkeypatch,
):
    at, m5, _ = _live(monkeypatch)
    _login(at, fm.PHYS)
    _open_record(at)
    text = _texts(at)
    assert fm.SERVER_PATIENT_REF in text  # the text comes from the server copy, not a fixture
    assert f"GET /records/{fm.RECORD_ID}" in m5.paths()
    assert f"POST /records/{fm.RECORD_ID}/verify" in m5.paths()
    assert at.button(key="approve").disabled
    _click(at, "yes_medications-0-dose_value")
    assert not at.button(key="approve").disabled
    _click(at, "approve")
    assert i18n.t("gate.saved", "en") in _texts(at)
    assert m5.save_bodies and set(m5.save_bodies[0]) == {"verdict_id", "resolutions"}
    assert m5.save_bodies[0]["resolutions"] == [
        {"check_id": "C4", "field_path": "/medications/0/dose_value", "action": "confirmed"}
    ]
    assert m5.save_bodies[0]["verdict_id"] == m5.latest
    assert f"POST /records/{fm.RECORD_ID}/save" in m5.paths()
    assert not any(p.endswith("/approve") for _, p in m5.calls)


def test_f4_after_a_save_nothing_can_be_answered_edited_or_approved_again(monkeypatch):
    at, _, _ = _live(monkeypatch)
    _login(at, fm.PHYS)
    _open_record(at)
    _click(at, "yes_medications-0-dose_value")
    _click(at, "approve")
    keys = {b.key for b in at.button}
    assert not [k for k in keys if k.startswith(("yes_", "no_", "undo_", "save_"))]
    assert at.button(key="approve").disabled
    assert i18n.t("approve.saved_locked", "en") in _texts(at)


def test_f4_mock_save_locks_the_record_too():
    at = _mock("rec-fx-asha-001")
    _click(at, "approve")
    assert i18n.t("gate.saved", "en") in _texts(at)
    assert at.button(key="approve").disabled
    assert not [b for b in at.button if b.key.startswith(("no_", "yes_"))]


def test_live_server_refusal_is_shown_and_nothing_is_saved(monkeypatch):
    m5 = fm.FakeM5()
    at, _, g = _live(monkeypatch, m5)
    _login(at, fm.PHYS)
    _open_record(at)
    _click(at, "yes_medications-0-dose_value")
    m5.fail_with = 409
    _click(at, "approve")
    text = _texts(at)
    assert i18n.t("gate.refused_title", "en") in text
    assert htmllib.escape(i18n.t("gate.code.refused_conflict", "en")) in text
    assert i18n.t("gate.saved", "en") not in text
    assert g.status(fm.RECORD_ID) is None


def test_live_pharmacist_gets_not_found_from_the_server(monkeypatch):
    at, _, _ = _live(monkeypatch)
    _login(at, fm.PHARM)
    _open_record(at)
    text = _texts(at)
    assert i18n.t("review.load_failed", "en") in text
    assert htmllib.escape(i18n.t("gate.code.not_found", "en")) in text


def test_live_edit_goes_to_the_server_and_new_verdict_is_shown(monkeypatch):
    m5 = fm.FakeM5()
    at, _, _ = _live(monkeypatch, m5)
    _login(at, fm.PHYS)
    _open_record(at)
    first = m5.latest
    _click(at, "no_medications-0-dose_value")
    at.number_input(key="in_medications-0-dose_value_dose_value").set_value(500.0)
    _click(at, "save_medications-0-dose_value")
    assert f"PATCH /records/{fm.RECORD_ID}" in m5.paths()
    assert m5.latest != first
    assert not at.button(key="approve").disabled  # the server's new verdict is clean
    _click(at, "approve")
    # the flags that were answered belong to the FIRST verdict
    assert m5.save_bodies[0]["verdict_id"] == first
    assert m5.save_bodies[0]["resolutions"][0]["action"] == "edited"


def test_live_expired_login_returns_to_the_login_screen(monkeypatch):
    at, m5, g = _live(monkeypatch)
    _login(at, fm.PHYS)
    _open_record(at)
    _click(at, "yes_medications-0-dose_value")
    m5.tokens.clear()  # the server no longer knows this token
    _click(at, "approve")
    assert not g.logged_in
    at.run()
    assert "login_submit" in {b.key for b in at.button}


# ------------------------------------------------------------------ F5, F6, F7, F8


def test_f5_env_refusal_cannot_be_switched_off_from_the_page(monkeypatch):
    monkeypatch.setenv("M6_MOCK_GATE_REFUSE", "1")
    at = _mock("rec-fx-asha-001")
    box = at.checkbox(key="force_refuse")
    assert box.disabled and box.value is True
    at.session_state["force_refuse"] = False  # forged: a disabled widget cannot be clicked
    at.run()
    _click(at, "approve")
    text = _texts(at)
    assert htmllib.escape(i18n.t("gate.code.refused_forced", "en")) in text
    assert i18n.t("gate.saved", "en") not in text


def test_f6_bidi_characters_in_a_record_are_made_visible(monkeypatch):
    m5 = fm.FakeM5(patient_ref=f"pt{BIDI}-0001")
    at, _, _ = _live(monkeypatch, m5)
    _login(at, fm.PHYS)
    _open_record(at)
    shown = "\n".join(e.value for e in at.html if not e.value.lstrip().startswith("<style"))
    assert BIDI not in shown and "[U+202E]" in shown
    assert i18n.t("review.bidi_found", "en") in _texts(at)


def test_f6_an_edit_with_a_bidi_character_is_refused():
    at = _mock("rec-fx-asha-002")
    _click(at, "no_medications-0-drug")
    at.text_input(key="in_medications-0-drug_drug").set_value(f"para{BIDI}cetamol")
    _click(at, "save_medications-0-drug")
    assert i18n.t("resolve.bidi", "en") in _texts(at)
    shown = "\n".join(e.value for e in at.html)
    assert BIDI not in shown


def test_f7_single_letter_drug_edit_stays_flagged_in_the_app():
    at = _mock("rec-fx-asha-002")
    _click(at, "no_medications-0-drug")
    at.text_input(key="in_medications-0-drug_drug").set_value("p")
    _click(at, "save_medications-0-drug")
    assert at.button(key="approve").disabled  # a new flag must be answered
    assert htmllib.escape(i18n.t("reason.C2", "en")) in _texts(at)


def test_f8_anti_framing_limitation_is_documented_and_bind_stays_loopback():
    readme = (M6 / "README.md").read_text(encoding="utf-8")
    assert "X-Frame-Options" in readme and "frame-ancestors" in readme
    cfg = (M6 / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert '"127.0.0.1"' in cfg


# ------------------------------------------------------------------ reason codes (D-112)


@pytest.mark.parametrize(
    "reason,key,cannot",
    [
        ("out_of_range [CR-DOSE]: x", "reason.code.out_of_range", False),
        ("exceeds_max_daily [CR-DOSE]: x", "reason.code.exceeds_max_daily", False),
        ("unit_not_allowed [CR-ROUTE]: x", "reason.code.route", False),
        ("unit_not_allowed [CR-DOSE]: x", "reason.code.unit_not_allowed", False),
        (
            "cannot_verify:paediatric [CR-PAEDIATRIC]: x",
            "reason.code.cannot_verify_paediatric",
            True,
        ),
        (
            "cannot_verify:liquid_strength [CR-LIQUID-STRENGTH]: x",
            "reason.code.cannot_verify_liquid_strength",
            True,
        ),
        ("cannot_verify:no_range [CR-DOSE]: x", "reason.code.cannot_verify_no_range", True),
        (
            "cannot_verify:not_in_lexicon [CR-DOSE]: x",
            "reason.code.cannot_verify_not_in_lexicon",
            True,
        ),
        ("cannot_verify:count_unit [CR-DOSE]: x", "reason.code.cannot_verify_count_unit", True),
        ("cannot_verify:something_new [CR-DOSE]: x", "reason.code.cannot_verify", True),
    ],
)
def test_c4_reason_codes_are_explained_in_both_languages(monkeypatch, reason, key, cannot):
    at, _, _ = _live(monkeypatch, fm.FakeM5(c4_reason=reason))
    _login(at, fm.PHYS)
    _open_record(at)
    text = _texts(at)
    for lang in ("kn", "en"):
        assert htmllib.escape(i18n.t(key, lang)) in text
        note = htmllib.escape(i18n.t("reason.cannot_verify_note", lang))
        assert (note in text) is cannot


# ------------------------------------------------------------------ record.v2 (read only)


def test_record_v2_new_fields_are_shown_read_only():
    at = _mock("rec2-fx-child-007-no-strength", lang="en")
    text = _texts(at)
    for k in ("v2.route", "v2.strength", "v2.formulation", "v2.status", "v2.as_needed"):
        assert htmllib.escape(i18n.t(k, "en")) in text
    assert i18n.t("v2val.form.syrup", "en") in text
    assert i18n.t("v2val.mstatus.prescribed", "en") in text
    assert i18n.t("v2val.age.child", "en") in text
    assert i18n.t("v2.read_only", "en") in text
    # no edit control for the v2 fields
    assert not [i for i in at.text_input if "route" in (i.key or "")]


def test_record_v1_still_works_without_v2_lines():
    at = _mock("rec-fx-asha-001")
    assert i18n.t("v2.route", "en") not in _texts(at)
