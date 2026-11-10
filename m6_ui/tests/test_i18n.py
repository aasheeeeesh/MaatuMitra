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
