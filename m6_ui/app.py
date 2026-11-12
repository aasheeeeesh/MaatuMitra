"""MaatuMitra review app (m6_ui, layers L4 + L6). Streamlit entry script.

Run (Git Bash, repo root):  mingw32-make m6-run      (MODE=mock by default; 127.0.0.1 only)
Every visible string comes from i18n/{kn,en}.json. All data text is escaped before it is
put into HTML (highlight.esc). Buttons use callbacks so state changes apply in one run.
"""

from __future__ import annotations

import copy
import io
import os
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from contracts.validate import validate_doc  # noqa: E402
from m6_ui import audio, data, failures, gate, highlight, i18n, review, theme, verifier  # noqa: E402
from m6_ui.highlight import esc  # noqa: E402

MODE = os.environ.get("MODE", "mock")
DEFAULT_RECORD = "rec-fx-pharm-003-asr"
ROLE_ICONS = {
    "asha": ":material/home_health:",
    "nurse": ":material/vaccines:",
    "physician": ":material/stethoscope:",
    "pharmacist": ":material/medication:",
}
NAV = [
    ("record", ":material/mic:", "nav.record"),
    ("review", ":material/fact_check:", "nav.review"),
    ("help", ":material/forum:", "nav.help"),
    ("fail", ":material/report:", "nav.fail"),
    ("font", ":material/translate:", "nav.font"),
]
ICON_FLAG, ICON_OK = "!", "✓"  # check mark (not Kannada); always paired with a text label
NOT_SURE = "__not_sure__"

ss = st.session_state


def t(key: str, **fmt) -> str:
    return i18n.t(key, ss.get("lang", i18n.DEFAULT_LANG), **fmt)


def html(markup: str) -> None:
    st.html(markup)


@st.cache_resource
def _catalogue() -> data.Catalogue:
    return data.Catalogue(ROOT)


# --------------------------------------------------------------------------- state + callbacks


def _init() -> None:
    # MOCK-only start defaults for screenshots/demos (env, never URL parameters)
    demo = MODE != "live"
    demo_role = os.environ.get("M6_DEMO_ROLE") if demo else None
    demo_lang = os.environ.get("M6_DEMO_LANG") if demo else None
    ss.setdefault("lang", demo_lang if demo_lang in i18n.LANGS else i18n.DEFAULT_LANG)
    ss.setdefault("role", demo_role if demo_role in i18n.ROLES else None)
    ss.setdefault("page", os.environ.get("M6_DEMO_PAGE", "record") if demo else "record")
    ss.setdefault(
        "record_id", os.environ.get("M6_DEMO_RECORD", DEFAULT_RECORD) if demo else DEFAULT_RECORD
    )
    ss.setdefault("load_failure", None)
    ss.setdefault("login_result", None)
    ss.setdefault("work", {})
    ss.setdefault("play", None)
    ss.setdefault("editing", None)
    ss.setdefault("help_choice", None)
    if "gate" not in ss:
        ss.gate = gate.make_gate()
    if "verifier" not in ss:
        ss.verifier = verifier.make_verifier()


def _set(**kw) -> None:
    for k, v in kw.items():
        ss[k] = v


def _role() -> str | None:
    """live: the role inside the person's own login token (never a click); mock: the practice pick."""
    return ss.gate.role if ss.gate.live else ss.get("role")


def _is_saved(record_id: str) -> bool:
    return ss.gate.status(record_id) == "saved"


def _new_work(record: dict, verdict: dict | None, vid: str | None, case: data.Case) -> dict:
    return {
        "record": copy.deepcopy(record),
        "verdict": copy.deepcopy(verdict),
        "vid": vid,  # latest verdict id (after edits)
        "base_vid": vid,  # verdict id first stored by the server: the flags the physician answers
        "base_flags": review.flags_from_verdict(verdict),
        "case": case,
        "resolved": {},
        "edited": [],
        "result": None,
        "reran": False,
        "error": None,
        "bidi": bool(data.bidi_problems(record)),
        "read_only": False,
        "resolutions": [],
    }


def _saved_work(d: dict, case: data.Case) -> dict:
    """Working state for an already saved record: stored verdict and answers, nothing to answer."""
    w = _new_work(d["record"], d["verdict"], d["verdict_id"], case)
    w["read_only"] = True
    # show the physician's stored answers on the rows they belong to (role filter is the server's)
    answers = {(r["check_id"], r["field_path"]): r["action"] for r in d.get("resolutions") or []}
    for f in review.flags_from_verdict(d["verdict"]):
        if (f.check_id, f.field_path) in answers:
            w["resolved"][f.flag_id] = answers[(f.check_id, f.field_path)]
    w["resolutions"] = list(d.get("resolutions") or []) if _role() == "physician" else []
    return w


def _work(record_id: str) -> dict | None:
    """Per-record working state. Live: the record and verdict are loaded from m5 by this same id."""
    if record_id in ss.work:
        return ss.work[record_id]
    if ss.gate.live:
        got = ss.gate.load_record(record_id)
        if not got.ok:
            ss.load_failure = got.result
            return None
        d = got.data
        case = _catalogue().case_for(d["record"], d["verdict"])
        if d.get("read_only"):
            w = _saved_work(d, case)
        else:
            w = _new_work(d["record"], d["verdict"], d["verdict_id"], case)
    else:
        case = _catalogue().case(record_id)
        if _is_saved(record_id):  # saved is final: show what the "server" stored, never verify
            got = ss.gate.review(record_id)
            w = _saved_work(got.data, case) if got.ok else None
            if w is None:
                ss.load_failure = got.result
                return None
        else:
            vid = (
                ss.gate.store_verdict(record_id, case.record, case.verdict)
                if case.verdict
                else None
            )
            w = _new_work(case.record, case.verdict, vid, case)
    ss.work[record_id] = w
    return w


def _rows(record_id: str) -> list[review.Row]:
    w = _work(record_id)
    return review.build_rows(w["record"], w["verdict"]) if w else []


def _row(record_id: str, path: str) -> review.Row | None:
    return next((r for r in _rows(record_id) if r.path == path), None)


def _go_review() -> None:
    if ss.gate.live:
        ss.record_id = (ss.get("live_record_id") or "").strip()
    else:
        ss.record_id = ss.get("fixture_pick", ss.record_id)
    ss.load_failure = None
    ss.page = "review"


def _do_login() -> None:
    res = ss.gate.login((ss.get("login_user") or "").strip(), ss.get("login_password") or "")
    ss.login_result = None if res.ok else res
    ss.login_password = ""
    if res.ok:
        ss.work, ss.record_id, ss.page = {}, "", "record"  # a new person starts clean


def _do_logout() -> None:
    ss.gate.logout()
    ss.work, ss.record_id, ss.page, ss.login_result = {}, "", "record", None


def _answer(path: str, how: str) -> None:
    if _is_saved(ss.record_id):
        return  # F4: a saved record is read-only
    row = _row(ss.record_id, path)
    if row is not None:
        review.mark_row(_work(ss.record_id)["resolved"], row, how)
    _work(ss.record_id)["result"] = None


def _undo(path: str) -> None:
    if _is_saved(ss.record_id):
        return
    row = _row(ss.record_id, path)
    if row is not None:
        review.unmark_row(_work(ss.record_id)["resolved"], row)
    _work(ss.record_id)["result"] = None


def _toggle_play(path: str) -> None:
    ss.play = None if ss.play == path else path


def _attr_path(row: review.Row, attr: str) -> str:
    return f"{row.item_path}/{attr}"


def _save_edit(path: str) -> None:
    rid = ss.record_id
    w = _work(rid)
    row = _row(rid, path)
    ss.editing = None
    if row is None or w is None or _is_saved(rid):
        return
    new_record, changed = w["record"], []
    for attr, kind, _label in review.EDIT_SPEC[row.kind]:
        ap = _attr_path(row, attr)
        val = ss.get(f"in_{row.slug}_{attr}")
        if kind == "number" and val is not None:
            val = int(val) if float(val).is_integer() else float(val)
            val = None if val == 0 else val
        if kind == "text":
            val = (val or "").strip() or review.get_pointer(new_record, ap)
        if val != review.get_pointer(new_record, ap):
            new_record = review.set_pointer(new_record, ap, val)
            changed.append(ap)
    if not changed:
        return
    if data.bidi_problems(new_record):  # F6: never accept direction-control characters
        w["error"] = "resolve.bidi"
        return
    if validate_doc(new_record.get("schema_version", "record.v1"), new_record):
        w["error"] = "resolve.invalid"
        return
    if ss.gate.live:  # the server stores the edit and verifies the stored result
        got = ss.gate.update_record(rid, new_record)
        if not got.ok:
            w["result"], w["error"] = got.result, None
            return
        verdict, vid = got.data["verdict"], got.data["verdict_id"]
    else:
        case = w["case"]
        verdict = ss.verifier.verify(
            new_record, case.transcript, case.verdict, set(w["edited"]) | set(changed)
        )
        vid = ss.gate.store_verdict(rid, new_record, verdict)
    review.mark_row(w["resolved"], row, "edited")
    w["record"], w["verdict"], w["vid"] = new_record, verdict, vid
    w["edited"] = sorted(set(w["edited"]) | set(changed))
    w["reran"], w["result"], w["error"] = True, None, None


def _can_approve(w: dict | None) -> bool:
    """The page's own rule; the server decides again. Physician only, nothing saved yet."""
    return bool(
        w
        and _role() == "physician"
        and not _is_saved(ss.record_id)
        and review.approve_enabled(w["verdict"], w["resolved"])
        and review.build_resolutions(w["base_flags"], w["resolved"]) is not None
    )


def _approve() -> None:
    rid = ss.record_id
    w = _work(rid)
    if not _can_approve(w):
        return  # never trust the disabled state alone
    res = review.build_resolutions(w["base_flags"], w["resolved"])
    # D-94: one call. Save = approve. No separate /approve call (F3). After an edit m5 wants the
    # verdict that held the flags (the first one); without an edit, the current verdict.
    vid = w["base_vid"] if any(r["action"] == "edited" for r in res) else w["vid"]
    w["result"] = ss.gate.save(rid, vid, res, _role())


# --------------------------------------------------------------------------- pieces


def _banner(cls: str, text: str, icon: str = "") -> None:
    mark = f'<span class="icon icon-{cls}" aria-hidden="true">{esc(icon)}</span> ' if icon else ""
    html(f'<div class="mm-banner {cls}">{mark}{esc(text)}</div>')


def _both(key: str) -> str:
    """The same sentence in both languages (the saved banner must never depend on the toggle)."""
    return " / ".join(i18n.t(key, lang) for lang in (ss.lang, i18n.other(ss.lang)))


def _resolutions_box(resolutions: list[dict]) -> None:
    items = "".join(
        f"<li><b>{esc(r['check_id'])}</b> {esc(r['field_path'])}: "
        f"{esc(t('badge.edited' if r['action'] == 'edited' else 'badge.confirmed'))}</li>"
        for r in resolutions
    )
    html(
        f'<div class="mm-card"><p><b>{esc(t("review.resolutions_title"))}</b></p><ul>{items}</ul></div>'
    )


def _header() -> None:
    html(theme.css())
    with st.container(horizontal=True, key="langbar"):
        for lang in i18n.LANGS:
            st.button(
                i18n.t(f"lang.{lang}", lang),
                key=f"lang_{lang}",
                type="primary" if ss.lang == lang else "secondary",
                on_click=_set,
                kwargs={"lang": lang},
            )
    html(
        f'<p class="mm-title">{esc(t("app.title"))}</p>'
        f'<p class="mm-sub">{esc(t("app.subtitle"))}</p>'
    )
    if ss.gate.live:
        _banner("mock", t("app.live_banner"))
    else:
        _banner("mock", t("app.mock_banner"))
    html(f'<p class="mm-sub">{esc(t("app.not_native"))}</p>')


def _role_picker() -> None:
    html(f'<p class="mm-h2">{esc(t("role.title"))}</p><p class="mm-sub">{esc(t("role.hint"))}</p>')
    for role in i18n.ROLES:
        st.button(
            i18n.t(f"role.{role}", ss.lang),
            key=f"role_{role}",
            icon=ROLE_ICONS[role],
            width="stretch",
            on_click=_set,
            kwargs={"role": role, "page": "record"},
        )


def _login_page() -> None:
    html(
        f'<p class="mm-h2">{esc(t("login.title"))}</p><p class="mm-sub">{esc(t("login.hint"))}</p>'
    )
    with st.form("login_form", border=True):
        st.text_input(t("login.user"), key="login_user")
        st.text_input(t("login.password"), type="password", key="login_password")
        st.form_submit_button(
            t("login.submit"),
            key="login_submit",
            type="primary",
            width="stretch",
            on_click=_do_login,
        )
    if ss.login_result is not None:
        _refusal_box(ss.login_result, show_status=False)


def _nav() -> None:
    role_name = i18n.t(f"role.{_role()}", ss.lang)
    with st.container(horizontal=True, key="rolebar", vertical_alignment="center"):
        html(f'<p class="mm-sub">{esc(t("role.current", role=role_name))}</p>')
        if ss.gate.live:
            st.button(t("login.logout"), key="logout", on_click=_do_logout)
        else:
            st.button(t("role.change"), key="role_change", on_click=_set, kwargs={"role": None})
    with st.container(horizontal=True, key="navbar"):
        for page, icon, key in NAV:
            st.button(
                i18n.t(key, ss.lang),
                key=f"nav_{page}",
                icon=icon,
                type="primary" if ss.page == page else "secondary",
                on_click=_set,
                kwargs={"page": page},
            )


# --------------------------------------------------------------------------- screen 2


def _wav_seconds(raw: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(raw)) as w:
            return round(w.getnframes() / w.getframerate(), 1)
    except (wave.Error, EOFError):
        return None


def _live_record_picker() -> None:
    """Live: only what m5 shows THIS login (row-level security). The record id is typed."""
    html(f'<p class="mm-h2">{esc(t("record.live_patients"))}</p>')
    got = ss.gate.patients()
    if not got.ok:
        _refusal_box(got.result)
    elif not got.data:
        _banner("mock", t("record.live_no_patients"))
    else:
        for p in got.data:
            html(f'<p class="mm-card">{esc(p.get("name_synthetic", ""))}</p>')
    st.text_input(t("record.live_id_label"), key="live_record_id")


def _page_record() -> None:
    html(f'<p class="mm-h2">{esc(t("record.title"))}</p>')
    rec = st.audio_input(t("record.mic_label"), key="audio_rec")
    up = st.file_uploader(
        t("record.upload_label"), type=["wav", "mp3", "m4a", "ogg", "webm"], key="audio_upload"
    )
    got = rec or up
    if got is None:
        _banner("flags", t("record.state_none"), ICON_FLAG)
    else:
        raw = got.getvalue()
        ss.audio_bytes = raw
        secs = _wav_seconds(raw)
        text = (
            t("record.state_have", seconds=secs)
            if secs is not None
            else t("record.state_have_unknown")
        )
        _banner("clean", text, ICON_OK)
        st.audio(raw)
    if ss.gate.live:
        _live_record_picker()
    else:
        _banner("mock", t("record.mock_note"))
        ids = _catalogue().record_ids(_role())
        st.selectbox(
            t("record.fixture_label"),
            ids,
            index=ids.index(ss.record_id) if ss.record_id in ids else 0,
            key="fixture_pick",
        )
    st.button(
        t("record.go_review"),
        key="go_review",
        type="primary",
        width="stretch",
        icon=":material/arrow_forward:",
        on_click=_go_review,
    )


# --------------------------------------------------------------------------- screen 3 + 4


def _num(v) -> str:
    if v is None:
        return t("value.empty")
    return str(int(v)) if float(v).is_integer() else str(v)


def _value_text(rec: dict, row: review.Row) -> str:
    k = row.kind
    if k == "record":
        return rec["record_id"]
    item = review.get_pointer(rec, row.item_path)
    if k == "symptom":
        return f"{item['name']}: {t('value.present') if item['present'] else t('value.absent')}"
    if k == "drug":
        return item["drug"]
    if k == "dose":
        return f"{_num(item['dose_value'])} {item['dose_unit'] or ''}".strip()
    if k == "frequency":
        return _num(item["frequency_per_day"])
    if k == "duration":
        return _num(item["duration_days"])
    if k == "med_negated":
        return t("value.not_take") if item["negated"] else t("value.take")
    if k == "advice":
        return f"{item['text']} ({t('value.do_not') if item['negated'] else t('value.do')})"
    return item["text"]  # follow_up


def _reason_key(flag: review.Flag) -> str:
    if flag.check_id == review.NO_VERDICT_CHECK:
        return f"reason.{flag.reason}"
    return f"reason.{flag.check_id}"


CODE_RE = re.compile(r"^([a-z_]+(?::[a-z_]+)?) \[(CR-[A-Z-]+)\]:")


def _specific_keys(flag: review.Flag) -> tuple[str | None, bool]:
    """m4 C4 reason code ('cannot_verify:paediatric [CR-PAEDIATRIC]: ...') -> (i18n key, cannot_verify)."""
    m = CODE_RE.match(flag.reason or "")
    if not m or flag.check_id != "C4":
        return None, False
    code, cls = m.groups()
    if code.startswith("cannot_verify"):
        key = "reason.code." + code.replace(":", "_")
        return (key if i18n.has(key) else "reason.code.cannot_verify"), True
    if code == "unit_not_allowed" and cls == "CR-ROUTE":
        return "reason.code.route", False
    key = f"reason.code.{code}"
    return (key if i18n.has(key) else None), False


def _reasons_html(row: review.Row) -> str:
    order = [ss.lang, i18n.other(ss.lang)]
    parts = [f'<div class="reasons"><p><b>{esc(t("reason.title"))}</b></p>']
    for f in row.flags:
        key, cannot = _specific_keys(f)
        key = key or _reason_key(f)
        for lang in order:
            parts.append(f'<p lang="{lang}"><b>{esc(f.check_id)}</b> {esc(i18n.t(key, lang))}</p>')
            if cannot:
                parts.append(
                    f'<p lang="{lang}">{esc(i18n.t("reason.cannot_verify_note", lang))}</p>'
                )
        if f.check_id != review.NO_VERDICT_CHECK:
            parts.append(f'<p class="raw">{esc(t("reason.raw"))} {esc(f.reason)}</p>')
    parts.append("</div>")
    return "".join(parts)


def _v2_label(group: str, value) -> str:
    if value is None:
        return t("value.empty")
    key = f"v2val.{group}.{value}"
    return t(key) if i18n.has(key) else str(value)


def _v2_drug_line(rec: dict, row: review.Row) -> str:
    """record.v2: route, strength, formulation, status, as_needed, food_timing (read only)."""
    if rec.get("schema_version") != "record.v2" or row.kind != "drug":
        return ""
    m = review.get_pointer(rec, row.item_path)
    sv, su = m.get("strength_value"), m.get("strength_unit")
    strength = t("value.empty") if sv is None else f"{_num(sv)} {su or ''}".strip()
    an = m.get("as_needed")
    asn = t("value.empty") if an is None else t("value.yes" if an else "value.no")
    items = [
        ("v2.route", _v2_label("route", m.get("route"))),
        ("v2.strength", strength),
        ("v2.formulation", _v2_label("form", m.get("formulation"))),
        ("v2.status", _v2_label("mstatus", m.get("status"))),
        ("v2.as_needed", asn),
        ("v2.food_timing", _v2_label("food", m.get("food_timing"))),
    ]
    cells = "".join(f"<li><b>{esc(t(k))}:</b> {esc(v)}</li>" for k, v in items)
    return f'<ul class="v2-details">{cells}</ul><p class="mm-sub">{esc(t("v2.read_only"))}</p>'


def _row_head(rec: dict, row: review.Row, state: str | None) -> str:
    if row.flags and state is None:
        cls, badge = (
            "row-flag",
            (
                f'<span class="badge badge-flag"><span class="icon icon-flag" aria-hidden="true">{ICON_FLAG}</span>'
                f"{esc(t('badge.flag'))}</span>"
            ),
        )
    elif row.flags:
        cls, badge = (
            "row-done",
            (
                f'<span class="badge badge-done"><span class="icon icon-done" aria-hidden="true">{ICON_OK}</span>'
                f"{esc(t('badge.edited' if state == 'edited' else 'badge.confirmed'))}</span>"
            ),
        )
    else:
        cls, badge = (
            "",
            (
                f'<span class="badge badge-ok"><span class="icon icon-ok" aria-hidden="true">{ICON_OK}</span>'
                f"{esc(t('badge.ok'))}</span>"
            ),
        )
    heard = ""
    if row.evidence:
        heard = f'<p class="heard" lang="kn">{esc(t("review.heard"))} &ldquo;{esc(row.evidence["span_text"])}&rdquo;</p>'
    reasons = _reasons_html(row) if row.flags else ""
    return (
        f'<div class="row-head {cls}" data-row-path="{esc(row.path)}" data-flagged="{1 if row.flags else 0}">'
        f"{badge}"
        f'<p class="field-name">{esc(t(f"field.{row.kind}"))}</p>'
        f'<p class="field-value">{esc(t("review.value"))} {esc(_value_text(rec, row))}</p>'
        f"{_v2_drug_line(rec, row)}{heard}{reasons}</div>"
    )


def _edit_form(rec: dict, row: review.Row) -> None:
    with st.form(key=f"form_{row.slug}", border=True):
        html(
            f'<p class="mm-h2">{esc(t("review.edit_title"))}</p><p class="mm-sub">{esc(t("resolve.edit_hint"))}</p>'
        )
        for attr, kind, label in review.EDIT_SPEC[row.kind]:
            cur = review.get_pointer(rec, _attr_path(row, attr))
            key = f"in_{row.slug}_{attr}"
            if kind == "number":
                st.number_input(
                    t(label),
                    value=None if cur is None else float(cur),
                    min_value=0.0,
                    step=1.0,
                    key=key,
                )
            elif kind == "text":
                st.text_input(t(label), value=cur or "", key=key)
            elif kind == "bool":
                st.radio(
                    t(label),
                    [True, False],
                    index=0 if cur else 1,
                    horizontal=True,
                    key=key,
                    format_func=lambda b: t("value.yes") if b else t("value.no"),
                )
            elif kind == "unit":
                st.selectbox(
                    t(label),
                    review.UNITS,
                    index=review.UNITS.index(cur) if cur in review.UNITS else 0,
                    key=key,
                    format_func=lambda u: u or t("value.empty"),
                )
        with st.container(horizontal=True):
            st.form_submit_button(
                t("resolve.save"),
                key=f"save_{row.slug}",
                type="primary",
                on_click=_save_edit,
                args=(row.path,),
            )
            st.form_submit_button(
                t("resolve.cancel"),
                key=f"cancel_{row.slug}",
                on_click=_set,
                kwargs={"editing": None},
            )


def _player(row: review.Row) -> None:
    ev = row.evidence or {}
    src = audio.fixture_bytes() if MODE != "live" else ss.get("audio_bytes")
    clip = audio.cut_wav(src, ev.get("audio_start"), ev.get("audio_end")) if src else None
    if clip is None:
        _banner("mock", t("play.no_timing"))
        return
    st.audio(clip, format="audio/wav", autoplay=True)
    if MODE != "live":
        html(f'<p class="mm-sub">{esc(t("play.mock_note"))}</p>')


def _render_row(rec: dict, row: review.Row, w: dict) -> None:
    state = review.row_state(w["resolved"], row)
    locked = _is_saved(ss.record_id)  # F4: nothing can be answered or edited after a save
    with st.container(key=f"row_{row.slug}"):
        html(_row_head(rec, row, state))
        with st.container(horizontal=True):
            if row.flags and state is None and not locked:
                st.button(
                    t("resolve.yes"),
                    key=f"yes_{row.slug}",
                    type="primary",
                    icon=":material/check:",
                    on_click=_answer,
                    args=(row.path, "confirmed"),
                )
            if row.flags and state is not None and not locked:
                st.button(
                    t("resolve.undo"),
                    key=f"undo_{row.slug}",
                    icon=":material/undo:",
                    on_click=_undo,
                    args=(row.path,),
                )
            if review.EDIT_SPEC[row.kind] and not locked:
                st.button(
                    t("resolve.no"),
                    key=f"no_{row.slug}",
                    icon=":material/edit:",
                    on_click=_set,
                    kwargs={"editing": row.path},
                )
            if row.evidence:
                st.button(
                    t("play.button"),
                    key=f"play_{row.slug}",
                    icon=":material/play_arrow:",
                    on_click=_toggle_play,
                    args=(row.path,),
                )
        if ss.play == row.path:
            _player(row)
        if ss.editing == row.path and not locked:
            _edit_form(rec, row)


def _refusal_box(res: gate.GateResult, show_status: bool = True) -> None:
    server = f"<p>{esc(t('gate.server_message'))} {esc(res.message)}</p>" if res.message else ""
    html(
        f'<div class="gate-result refused" role="alert"><p class="title"><span class="icon icon-flag">{ICON_FLAG}</span> '
        f"{esc(t('gate.refused_title'))}</p><p>{esc(t(f'gate.code.{res.code}'))}</p>{server}"
        f"{'<p>' + esc(t('gate.status', status=t('status.not_saved'))) + '</p>' if show_status else ''}</div>"
    )


def _gate_result(res: gate.GateResult) -> None:
    if res.ok or res.code == "already_saved":  # F4: a repeat on a saved record is not a refusal
        html(
            f'<div class="gate-result saved"><p class="title"><span class="icon icon-ok">{ICON_OK}</span> '
            f"{esc(t('gate.saved'))}</p><p>{esc(t('gate.status', status=t('status.saved')))}</p></div>"
        )
        return
    _refusal_box(res)


def _page_review() -> None:
    rid = ss.record_id
    if not ss.gate.live and rid not in _catalogue().record_ids(_role()):
        _banner("flags", t("review.no_record"), ICON_FLAG)
        return
    if ss.gate.live and not rid:
        _banner("flags", t("review.no_record"), ICON_FLAG)
        return
    w = _work(rid)
    if w is None:  # live: the server refused or does not know this record
        _banner("flags", t("review.load_failed"), ICON_FLAG)
        if ss.load_failure is not None:
            _refusal_box(ss.load_failure, show_status=False)
        return
    case = w["case"]
    rec = w["record"]
    rows = review.build_rows(rec, w["verdict"])
    enc = t(f"encounter.{rec['encounter_type']}")
    html(
        f'<p class="mm-h2">{esc(t("review.title"))}</p>'
        f'<p class="mm-sub">{esc(t("review.meta", record_id=rec["record_id"], patient_ref=rec["patient_ref"], encounter=enc))}</p>'
    )
    if w["read_only"] or _is_saved(rid):
        _banner("clean", _both("review.saved_readonly"), ICON_OK)
        if w["verdict"] is None:
            _banner("mock", t("review.no_stored_verdict"))
        if w["resolutions"]:
            _resolutions_box(w["resolutions"])
    if case.errors and not w["read_only"]:
        _banner("flags", t("review.load_errors", errors=", ".join(case.errors)), ICON_FLAG)
    if w["bidi"]:
        _banner("flags", t("review.bidi_found"), ICON_FLAG)
    if rec.get("schema_version") == "record.v2":
        age = (rec.get("patient_age_band") or {}).get("band")
        wt = (rec.get("weight_kg") or {}).get("value")
        html(
            f'<p class="mm-sub"><b>{esc(t("v2.age_band"))}:</b> {esc(_v2_label("age", age))} | '
            f"<b>{esc(t('v2.weight'))}:</b> {esc(_num(wt))}</p>"
        )
    open_rows = [r for r in rows if r.flags and review.row_state(w["resolved"], r) is None]
    if any(r.flags for r in rows):
        _banner("flags", t("review.summary_flags", n=len([r for r in rows if r.flags])), ICON_FLAG)
    else:
        _banner("clean", t("review.summary_clean"), ICON_OK)
    if w["reran"]:
        _banner("mock", t("review.verifier_rerun"))
    if w.get("error"):
        _banner("flags", t(w["error"]), ICON_FLAG)

    html(
        f'<p class="mm-h2">{esc(t("review.transcript"))}</p><p class="mm-sub">{esc(t("review.legend"))}</p>'
    )
    if case.transcript is not None:
        spans = highlight.spans_for_record(rec, w["verdict"])
        html(highlight.render_transcript(case.transcript["text"], spans))
    else:
        _banner("flags", t("error.load_transcript"), ICON_FLAG)

    html(f'<p class="mm-h2">{esc(t("review.fields"))}</p>')
    for row in rows:
        _render_row(rec, row, w)

    saved = _is_saved(rid)
    enabled = _can_approve(w)
    html(f'<p class="mm-sub">{esc(t("approve.never_auto"))}</p>')
    if saved:
        _banner("clean", t("approve.saved_locked"), ICON_OK)
    elif _role() != "physician":
        _banner("flags", t("approve.physician_only"), ICON_FLAG)
    elif enabled:
        _banner("clean", t("approve.ready"), ICON_OK)
    else:
        _banner("flags", t("approve.blocked", n=max(len(open_rows), 1)), ICON_FLAG)
    st.button(
        t("approve.button"),
        key="approve",
        type="primary",
        disabled=not enabled,
        width="stretch",
        icon=":material/verified:",
        on_click=_approve,
    )
    if w["result"] is not None:
        _gate_result(w["result"])
    if not ss.gate.live:
        html(f'<p class="mm-sub">{esc(t("demo.title"))}</p>')
        locked = ss.gate.locked
        st.checkbox(
            t("demo.force_refuse"), value=ss.gate.force_refuse, key="force_refuse", disabled=locked
        )
        ss.gate.force_refuse = bool(ss.force_refuse)  # a locked gate ignores "off" (F5)
        if locked:
            html(f'<p class="mm-sub">{esc(t("demo.locked"))}</p>')


# --------------------------------------------------------------------------- screen 5


def _page_help() -> None:
    html(f'<p class="mm-h2">{esc(t("help.title"))}</p>')
    _banner("mock", t("help.placeholder"))
    with st.container(horizontal=True):
        st.audio_input(t("help.voice_label"), key="help_voice")
    html(
        f'<p class="mm-sub">{esc(t("help.voice_note"))}</p><p class="mm-h2">{esc(t("help.pick"))}</p>'
    )
    cards = _catalogue().cards()
    for card in cards:
        st.button(
            card["topic"],
            key=f"card_{card['id']}",
            width="stretch",
            icon=":material/description:",
            on_click=_set,
            kwargs={"help_choice": card["id"]},
        )
    st.button(
        t("help.not_sure"),
        key="help_not_sure",
        type="primary",
        width="stretch",
        icon=":material/help:",
        on_click=_set,
        kwargs={"help_choice": NOT_SURE},
    )
    choice = ss.help_choice
    if choice == NOT_SURE:
        html(
            f'<div class="ask-doctor" role="alert"><p class="title"><span class="icon icon-flag">?</span> '
            f"{esc(t('help.ask_doctor_title'))}</p><p>{esc(t('help.ask_doctor_body'))}</p></div>"
        )
    elif choice:
        card = next((c for c in cards if c["id"] == choice), None)
        if card:
            status = (
                t("help.card_status_machine")
                if card["status"].startswith("machine")
                else t("help.card_status_verbatim")
            )
            html(
                f'<div class="mm-card"><p lang="kn">{esc(card["kn_text"])}</p><p lang="en">{esc(card["en_text"])}</p>'
                f'<p class="mm-sub">{esc(status)}</p>'
                f'<p class="mm-sub">{esc(t("help.source"))} {esc(card["source_url"])}</p></div>'
            )
            if card["clinician_reviewed"]:
                _banner("clean", t("help.clinician"), ICON_OK)
            else:  # the "not checked" state is loud: red box + icon + words (K8)
                _banner("flags", t("help.not_clinician"), ICON_FLAG)


# --------------------------------------------------------------------------- screen 6 + font page


def _page_fail() -> None:
    html(f'<p class="mm-h2">{esc(t("fail.title"))}</p><p>{esc(t("fail.intro"))}</p>')
    _banner("flags", t("fail.blind_spot"), ICON_FLAG)
    for r in failures.load_failures(ROOT):
        lines = [
            f"<p><b>{esc(r.type_name)}</b> | {esc(r.condition)}</p>",
            f'<p class="mm-sub">{esc(t("fail.measured") if r.measured else t("fail.not_measured"))}</p>',
        ]
        if r.n:
            lines.append(f"<p>{esc(t('fail.caught', caught=r.caught, n=r.n))}</p>")
        if r.n_unique is not None:
            lines.append(
                f"<p>{esc(t('fail.unique', unique_caught=r.unique_caught, n_unique=r.n_unique))}</p>"
            )
        for ex in r.examples:
            lines.append(f"<p>{esc(t('fail.example'))} {esc(ex)}</p>")
        if r.text:
            lines.append(f"<pre>{esc(r.text)}</pre>")
        lines.append(f'<p class="mm-sub">{esc(t("fail.source"))} {esc(r.source)}</p>')
        html('<div class="mm-card fail-row">' + "".join(lines) + "</div>")


def _page_font() -> None:
    import json

    items = json.loads((Path(__file__).with_name("conjuncts.json")).read_text(encoding="utf-8"))[
        "items"
    ]
    html(f'<p class="mm-h2">{esc(t("font.title"))}</p><p>{esc(t("font.intro"))}</p>')
    _banner("mock", t("font.note"))
    for it in items:
        cps = " ".join(f"U+{ord(c):04X}" for c in it["text"])
        html(
            f'<div class="mm-card"><p class="conj" lang="kn">{esc(it["text"])}</p>'
            f'<p class="cps">{esc(t("font.codepoints"))} {cps}</p><p class="cps">{esc(it["what"])}</p></div>'
        )


# --------------------------------------------------------------------------- main


def main() -> None:
    _init()
    st.set_page_config(
        page_title=t("app.title"), layout="centered", initial_sidebar_state="collapsed"
    )
    addr = st.get_option("server.address")
    if addr not in (None, "", "127.0.0.1", "localhost", "::1"):
        st.error(t("app.bind_refused"))
        st.stop()
    _header()
    if ss.gate.live:
        if not ss.gate.logged_in:
            _login_page()
            return
        if _role() not in i18n.ROLES:
            _banner("flags", t("login.role_unsupported"), ICON_FLAG)
            st.button(t("login.logout"), key="logout", on_click=_do_logout)
            return
    elif not ss.get("role"):
        _role_picker()
        return
    _nav()
    {
        "record": _page_record,
        "review": _page_review,
        "help": _page_help,
        "fail": _page_fail,
        "font": _page_font,
    }.get(ss.page, _page_record)()


main()
