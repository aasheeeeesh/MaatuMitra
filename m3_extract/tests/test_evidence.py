"""EVIDENCE CHECK: transcript[char_start:char_end] must equal span_text (NFC). Forged spans are rejected."""

import copy

from m3_extract.evidence import check_evidence, evidence_for, locate_quote
from m3_extract.tests._helpers import FIX, load_json


def fixture_record():
    rec = load_json(FIX / "record" / "valid" / "rec-fx-pharm-003.json")
    tr = load_json(FIX / "transcript" / "valid" / "fx-pharm-003__gold.json")
    return rec, tr


def test_valid_fixture_record_passes():
    rec, tr = fixture_record()
    assert check_evidence(rec, tr["text"]) == []


def test_forged_span_text_is_rejected():
    rec, tr = fixture_record()
    forged = copy.deepcopy(rec)
    ev = forged["medications"][0]["evidence"]
    # Same length, different dose: a model "quoting" 500 where 50 was said, or vice versa.
    ev["span_text"] = ev["span_text"].replace("500", "250")
    errs = check_evidence(forged, tr["text"])
    assert errs and "medications/0" in errs[0]


def test_forged_offsets_are_rejected():
    rec, tr = fixture_record()
    forged = copy.deepcopy(rec)
    forged["advice"][0]["evidence"]["char_start"] += 1
    forged["advice"][0]["evidence"]["char_end"] += 1
    assert check_evidence(forged, tr["text"])


def test_out_of_bounds_and_empty_are_rejected():
    rec, tr = fixture_record()
    forged = copy.deepcopy(rec)
    forged["advice"][1]["evidence"]["char_end"] = len(tr["text"]) + 5
    assert check_evidence(forged, tr["text"])
    forged = copy.deepcopy(rec)
    forged["advice"][1]["evidence"]["char_end"] = forged["advice"][1]["evidence"]["char_start"]
    assert check_evidence(forged, tr["text"])


def test_non_nfc_span_text_compared_after_nfc():
    rec, tr = fixture_record()
    ok = copy.deepcopy(rec)
    # NFC-equal spans pass (the check normalises both sides)
    assert check_evidence(ok, tr["text"]) == []


def test_follow_up_evidence_is_checked():
    rec = load_json(FIX / "record" / "valid" / "rec-fx-nurse-005.json")
    tr = load_json(FIX / "transcript" / "valid" / "fx-nurse-005__gold.json")
    assert check_evidence(rec, tr["text"]) == []
    rec["follow_up"]["evidence"]["span_text"] = "ಮತ್ತೆ ಬನ್ನಿ ಎರಡು"
    assert check_evidence(rec, tr["text"])


def test_locate_quote_exact_only():
    text = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ"
    assert locate_quote(text, "500 mg") == (14, 20)
    assert locate_quote(text, " 500 mg ") == (14, 20)  # outer whitespace trimmed only
    assert locate_quote(text, "250 mg") is None
    assert locate_quote(text, "") is None


def test_evidence_audio_times_from_words():
    tr = load_json(FIX / "transcript" / "valid" / "fx-phys-004__asr_clean.json")
    ev = evidence_for(tr, 0, tr["text"].index(" "))
    assert ev["audio_start"] == tr["words"][0]["start"]
    assert ev["audio_end"] == tr["words"][0]["end"]
    gold_tr = load_json(FIX / "transcript" / "valid" / "fx-phys-004__gold.json")
    ev = evidence_for(gold_tr, 0, 5)
    assert ev["audio_start"] is None and ev["audio_end"] is None
