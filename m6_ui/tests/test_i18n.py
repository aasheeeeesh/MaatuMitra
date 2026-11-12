"""All strings externalised; kn/en key parity; no hard-coded Kannada in .py files."""

from __future__ import annotations

import regex

from m6_ui import i18n
from m6_ui.tests.helpers import M6, load_json

KANNADA = regex.compile(r"[\u0C80-\u0CFF]")
LITERAL_KEY = regex.compile(r"""\bt\(\s*["']([A-Za-z0-9_.]+)["']""")


def test_no_hard_coded_kannada_in_python_files():
    offenders = []
    for py in M6.rglob("*.py"):
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if KANNADA.search(line):
                offenders.append(f"{py.relative_to(M6)}:{n}")
    assert offenders == [], f"hard-coded Kannada found: {offenders}"


def _keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        out |= _keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
    return out


def test_kn_and_en_have_identical_keys_and_are_versioned():
    kn = load_json(M6 / "i18n" / "kn.json")
    en = load_json(M6 / "i18n" / "en.json")
    assert _keys(kn) == _keys(en)
    for doc in (kn, en):
        assert doc["_meta"]["version"]
        assert doc["_meta"]["native_validated"] is False
    for k in _keys(kn) - {k for k in _keys(kn) if k.startswith("_meta.")}:
        assert i18n.t(k, "kn").strip(), f"empty kn string {k}"
        assert i18n.t(k, "en").strip(), f"empty en string {k}"


def test_kannada_file_really_contains_kannada():
    kn = load_json(M6 / "i18n" / "kn.json")
    texts = [i18n.t(k, "kn") for k in _keys(kn) if not k.startswith("_meta.")]
    share = sum(bool(KANNADA.search(s)) for s in texts) / len(texts)
    assert share > 0.8


def test_every_literal_key_used_in_code_exists():
    used = set()
    for py in M6.rglob("*.py"):
        if "tests" in py.parts:
            continue
        used |= set(LITERAL_KEY.findall(py.read_text(encoding="utf-8")))
    assert used, "no t('...') calls found"
    missing = [k for k in sorted(used) if not i18n.has(k)]
    assert missing == []


def test_dynamic_keys_exist():
    for cid in ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "none", "no_verdict"]:
        assert i18n.has(f"reason.{cid}")
    for role in i18n.ROLES:
        assert i18n.has(f"role.{role}")
    for enc in [
        "asha_household_visit",
        "nurse_consult",
        "physician_consult",
        "pharmacist_dispensing",
    ]:
        assert i18n.has(f"encounter.{enc}")
    for st in ["draft", "flagged", "approved", "saved", "not_saved"]:
        assert i18n.has(f"status.{st}")
    from m6_ui import gate, review

    for code in gate.ALL_CODES:
        assert i18n.has(f"gate.code.{code}")
    for kind in review.KINDS:
        assert i18n.has(f"field.{kind}")


def test_format_placeholders_match_between_languages():
    ph = regex.compile(r"\{([a-z_]+)\}")
    kn = load_json(M6 / "i18n" / "kn.json")
    for k in _keys(kn):
        if k.startswith("_meta."):
            continue
        assert set(ph.findall(i18n.t(k, "kn", raw=True))) == set(
            ph.findall(i18n.t(k, "en", raw=True))
        ), k


def test_missing_key_fails_loudly():
    import pytest

    with pytest.raises(KeyError):
        i18n.t("does.not.exist", "en")


def test_new_reason_code_and_v2_keys_exist_and_text_is_nfc():
    import unicodedata

    for code in (
        "out_of_range exceeds_max_daily unit_not_allowed route cannot_verify "
        "cannot_verify_paediatric cannot_verify_no_range cannot_verify_not_in_lexicon "
        "cannot_verify_liquid_strength cannot_verify_count_unit"
    ).split():
        assert i18n.has(f"reason.code.{code}"), code
    for grp, vals in {
        "age": "infant child adolescent adult older_adult unknown",
        "route": "oral iv im sc topical inhaled rectal injection_unspecified other unknown",
        "form": "tablet capsule syrup suspension drops injection sachet other",
        "mstatus": "prescribed already_taken not_taken advised_against stopped_early continue_existing unknown",
        "food": "before_food after_food with_food empty_stomach",
    }.items():
        for v in vals.split():
            assert i18n.has(f"v2val.{grp}.{v}"), (grp, v)
    for lang in i18n.LANGS:
        for k, v in i18n.load(lang).items():
            if isinstance(v, str):
                assert unicodedata.is_normalized("NFC", v), (lang, k)


def test_accepted_kannada_review_fixes_are_applied():
    kn = lambda k: i18n.t(k, "kn", raw=True)  # noqa: E731
    assert kn("approve.ready").index("\u0c86\u0ca6\u0cb0\u0cc2") < kn("approve.ready").index(
        "\u0cb8\u0cb0\u0ccd\u0cb5\u0cb0\u0ccd"
    )  # "aadaru" before "server"
    assert "\u0c89\u0cb2\u0ccd\u0c9f\u0cbe" in kn("reason.C3")  # 'ulta' = reversed
    assert "\u0c87\u0ca6\u0cc6" in kn("reason.C4") and "\u0ca1\u0ccb\u0cb8\u0ccd" in kn("reason.C4")
    assert (
        kn("badge.ok") != "\u0caa\u0cb0\u0cbf\u0cb6\u0cc0\u0cb2\u0c95: \u0cb8\u0cb0\u0cbf"
    )  # old text
    assert "\u0cb8\u0cb0\u0cbf" not in kn("badge.ok").split(":")[-1]  # no 'correct' word
    assert "\u0c9a\u0cbf\u0c95\u0cbf\u0ca4\u0ccd\u0cb8\u0cc6" in kn(
        "app.mock_banner"
    )  # 'treatment'
    assert "\u0cac\u0cc7\u0ca1" in kn("fail.blind_spot")  # also 'bEDa'
    assert "\u0ca4\u0cc6\u0cb0\u0cc6\u0ca6" not in kn(
        "gate.code.refused_unresolved_flags"
    )  # calque
    assert kn("help.not_clinician") != kn("help.clinician")
    assert len(kn("help.not_clinician")) > len(kn("help.clinician")) + 15
    assert not regex.search(r"[A-Za-z]", i18n.t("error.load_transcript", "kn"))
    assert not i18n.has("error.load")
