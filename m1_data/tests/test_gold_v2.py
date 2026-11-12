"""gold.v2 (D-122, D-125..D-130): labels derived from the TEMPLATES, not guessed from text.

Written before m1_data/goldv2.py. What is proved here:
  * 592 gold.v2 files, valid against contracts gold.v2 (schema + span checks + speaker rule)
  * gold.v2 only ADDS fields to gold.v1 (turns, tags, symptoms, advice text, follow-up and the v1
    medication fields are unchanged)
  * status / route / formulation / age / as_needed / food_timing follow the template's intent
  * the lock only gained lines (git), dev files are not locked, an edited v2 test file is caught
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter

import pytest
import regex

from contracts.validate import SPEAKER_FROM_ROLE, conversation_text, validate_doc
from m1_data.goldv2 import med_fields
from m1_data.split import LOCK_PATH, read_lock, verify_lock

from .conftest import DATA, ROOT

V2 = DATA / "gold_v2"


@pytest.fixture(scope="module")
def v2(split_ids):
    out = {}
    for s, ids in split_ids.items():
        for cid in ids:
            out[cid] = (s, json.loads((V2 / f"{cid}.json").read_text("utf-8")))
    return out


def _tid(cid: str) -> str:
    return cid.split("-")[1]


def _meds(v2, tids):
    for cid, (_, d) in v2.items():
        if _tid(cid) in tids:
            for m in d["gold_record"]["medications"]:
                yield cid, d, m


def test_every_conversation_has_a_valid_gold_v2(v2, gold_docs):
    assert len(v2) == len(gold_docs) == 592
    for cid, (_, d) in v2.items():
        assert validate_doc("gold.v2", d) == [], cid
        assert d["schema_version"] == "gold.v2"


def test_v2_only_adds_to_v1(v2, gold_docs):
    for cid, (_, d) in v2.items():
        g = gold_docs[cid]
        for k in ("conversation_id", "template_family_id", "turns", "tags"):
            assert d[k] == g[k], (cid, k)
        a, b = d["gold_record"], g["gold_record"]
        for k in ("patient_ref", "encounter_type", "symptoms", "follow_up"):
            assert a[k] == b[k], (cid, k)
        assert [{k: x[k] for k in ("text", "negated", "gold_span")} for x in a["advice"]] == b[
            "advice"
        ]
        assert len(a["medications"]) == len(b["medications"])
        for m2, m1 in zip(a["medications"], b["medications"], strict=True):
            assert {k: m2[k] for k in m1} == m1, cid


def test_speaker_is_the_role_of_the_span_turn(v2):
    for cid, (_, d) in v2.items():
        for item in d["gold_record"]["medications"] + d["gold_record"]["advice"]:
            role = d["turns"][item["gold_span"]["turn_index"]]["speaker_role"]
            assert item["speaker"] == SPEAKER_FROM_ROLE[role], cid


def test_answer_templates_status_follows_the_answer(v2):
    """b*, c1..c4: the ಇಲ್ಲ / ಹೌದು answer decides the status; the evidence IS the answer."""
    n = Counter()
    for cid, d, m in _meds(v2, {"b1", "b2", "b3", "b5"}):
        text = conversation_text(d["turns"])
        ev = m["gold_field_spans"]["status"]
        assert text[ev["char_start"] : ev["char_end"]] == ev["span_text"]
        if m["negated"]:
            assert m["status"] == "not_taken", cid
            assert ev["span_text"] in {"ಇಲ್ಲ", "ಇಲ್ಲಾ"}, (cid, ev)
            # the answer comes in the turn AFTER the question
            assert ev["turn_index"] == m["gold_span"]["turn_index"] + 1
        else:
            assert m["status"] == "already_taken", cid
            assert ev["span_text"] == "ಹೌದು"
        n[m["status"]] += 1
    assert n["not_taken"] >= 15 and n["already_taken"] >= 3, n


def test_stopped_early_family(v2):
    n = 0
    for cid, d, m in _meds(v2, {"c1", "c2", "c3", "c4"}):
        assert m["status"] == ("stopped_early" if m["negated"] else "already_taken"), cid
        n += m["status"] == "stopped_early"
    assert n >= 10


def test_advised_against_and_prescribed(v2):
    seen = Counter()
    for cid, d, m in _meds(v2, {"c5", "d2", "d4", "f6", "g3", "i7"}):
        if _tid(cid) == "g3" and m["gold_span"]["turn_index"] != 1:
            continue
        if _tid(cid) == "i7" and m["dose_value"] is not None:
            continue
        if _tid(cid) == "g3" and m["dose_value"] is not None:
            continue
        assert m["status"] == ("advised_against" if m["negated"] else "prescribed"), cid
        seen[m["status"]] += 1
    assert seen["advised_against"] >= 10 and seen["prescribed"] >= 2, seen
    for cid, d, m in _meds(v2, {"d1", "d5", "e1", "e2", "e3", "g1", "g2", "h1", "h4", "h6", "i2"}):
        assert m["status"] == "prescribed" and m["negated"] is False, cid


def test_past_tense_gave_is_already_taken(v2):
    ms = list(_meds(v2, {"a3"}))
    assert ms
    for _cid, _d, m in ms:
        assert m["status"] == "already_taken"
        assert m["gold_field_spans"]["status"]["span_text"] == "ಕೊಟ್ಟೆ"


def test_identity_question_has_unknown_status_and_no_evidence(v2):
    ms = [m for _c, _d, m in _meds(v2, {"e5"}) if m["dose_value"] is None]
    assert ms
    for m in ms:
        assert m["status"] == "unknown" and "status" not in m["gold_field_spans"]


def test_status_values_cover_the_designed_set(v2):
    c = Counter(m["status"] for _s, d in v2.values() for m in d["gold_record"]["medications"])
    for want in ("prescribed", "already_taken", "not_taken", "advised_against", "stopped_early"):
        assert c[want] >= 10, c
    assert c["continue_existing"] == 0  # no template says "continue" (reported, not invented)


def test_route_and_formulation(v2):
    syrup = inj = tab = 0
    for cid, (_s, d) in v2.items():
        text = conversation_text(d["turns"])
        for m in d["gold_record"]["medications"]:
            fs = m["gold_field_spans"]
            if m["formulation"] == "syrup":
                syrup += 1
                assert fs["formulation"]["span_text"] == "ಸಿರಪ್", cid
                assert m["route"] == "oral" and fs["route"]["span_text"] == "ಸಿರಪ್"
            elif m["formulation"] == "injection":
                inj += 1
                assert fs["formulation"]["span_text"] == "injection"
                assert m["route"] == "injection_unspecified", cid
            elif m["formulation"] == "tablet":
                tab += 1
                assert fs["formulation"]["span_text"] in {"ಮಾತ್ರೆ", "Tablet"}, cid
                assert m["route"] == "oral"
            if m["dose_unit"] == "ml":  # liquid dose: syrup stated in the sentence
                assert m["formulation"] == "syrup", cid
            if m["formulation"] is None:
                assert "formulation" not in fs
            for sp in fs.values():
                assert text[sp["char_start"] : sp["char_end"]] == sp["span_text"]
    assert syrup >= 20 and inj >= 3 and tab >= 40, (syrup, inj, tab)


def test_every_injection_template_conversation_says_injection(v2):
    for _cid, d, m in _meds(v2, {"g7"}):
        if m["gold_span"]["turn_index"] == 0:
            assert m["formulation"] == "injection" and m["route"] == "injection_unspecified"


def test_liquid_doses_have_no_strength_because_the_sentence_never_says_it(v2):
    liquid = [
        m
        for _s, d in v2.values()
        for m in d["gold_record"]["medications"]
        if m["dose_unit"] == "ml"
    ]
    assert len(liquid) >= 20
    assert all(m["strength_value"] is None and m["strength_unit"] is None for m in liquid)
    assert all("strength" not in m["gold_field_spans"] for m in liquid)
    # both splits hold liquid doses, so the CR-LIQUID-STRENGTH check can be exercised on dev and test
    by_split = Counter(
        s for s, d in v2.values() for m in d["gold_record"]["medications"] if m["dose_unit"] == "ml"
    )
    assert by_split["dev"] >= 5 and by_split["test"] >= 5, by_split


def test_age_band_child_only_where_the_word_child_is_spoken(v2):
    n_child = 0
    for cid, (_s, d) in v2.items():
        text = conversation_text(d["turns"])
        age = d["gold_record"]["patient_age_band"]
        assert d["gold_record"]["weight_kg"] is None
        if regex.search(r"ಮಗು", text):
            assert age is not None and age["band"] == "child", cid
            sp = age["gold_span"]
            assert sp["span_text"].startswith("ಮಗು")
            assert text[sp["char_start"] : sp["char_end"]] == sp["span_text"]
            n_child += 1
        else:
            assert age is None, cid  # nobody says "adult": no evidence, so no label
    assert n_child >= 100


def test_as_needed_and_food_timing(v2):
    asn = [(cid, m) for cid, d, m in _meds(v2, {"g5", "i5"}) if m["as_needed"] is not None]
    assert asn and all(m["as_needed"] is True for _c, m in asn)
    assert {m["gold_field_spans"]["as_needed"]["span_text"] for _c, m in asn} <= {
        "fever ಇದ್ದರೆ ಮಾತ್ರ",
        "ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ",
    }
    n = Counter(
        _tid(cid)
        for cid, (_s, d) in v2.items()
        for m in d["gold_record"]["medications"]
        if m["as_needed"]
    )
    assert set(n) == {"g5", "i5"}
    food = [m for _c, d, m in _meds(v2, {"e1", "e2", "e4", "g2", "i3"}) if m["food_timing"]]
    assert food and all(m["food_timing"] == "after_food" for m in food)
    assert all(m["gold_field_spans"]["food_timing"]["span_text"] == "ಊಟದ ನಂತರ" for m in food)


def test_trailing_punctuation_is_not_part_of_evidence(v2):
    for _cid, (_s, d) in v2.items():
        for m in d["gold_record"]["medications"]:
            for sp in m["gold_field_spans"].values():
                assert sp["span_text"] == sp["span_text"].strip(" .,?")


def test_med_fields_strength_is_only_set_when_the_template_says_so():
    """The derivation helper, with a synthetic item (no shipped template states a strength)."""
    spans = {"m1": (0, 0, 20), "x1": (0, 5, 15), "t1": (0, 21, 27)}

    def span(mid):
        k, s, e = spans[mid]
        return {"turn_index": k, "span_text": "x" * (e - s), "char_start": s, "char_end": e}

    item = {
        "kind": "medication",
        "span": "m1",
        "slot": "D1",
        "status": "prescribed",
        "status_span": "t1",
        "strength": {"value": 120, "unit": "mg/5ml"},
        "strength_span": "x1",
    }
    out = med_fields(item, negative=False, span=span, has_span=lambda m: m in spans)
    assert (out["strength_value"], out["strength_unit"]) == (120, "mg/5ml")
    assert out["gold_field_spans"]["strength"]["char_start"] == 5
    item.pop("strength")
    item.pop("strength_span")
    out = med_fields(item, negative=False, span=span, has_span=lambda m: m in spans)
    assert out["strength_value"] is None and out["strength_unit"] is None
    assert "strength" not in out["gold_field_spans"]
    with pytest.raises(ValueError):  # non-unknown status without evidence is a template bug
        med_fields(
            {**item, "status_span": None}, negative=False, span=span, has_span=lambda m: False
        )


def test_every_medication_item_in_every_template_declares_its_status():
    from m1_data.templates import load_templates

    n = 0
    for t in load_templates():
        for it in t.items:
            if it["kind"] != "medication":
                continue
            n += 1
            assert "status" in it or {"status_neg", "status_pos"} <= set(it), t.id
    assert n >= 50


# ---------------------------------------------------------------- manifest and lock


def test_manifest_rows_for_gold_v2(manifest_rows, split_ids):
    rows = {r["file"]: r for r in manifest_rows}
    import hashlib

    for s, ids in split_ids.items():
        for cid in ids:
            r = rows[f"data/gold_v2/{cid}.json"]
            p = V2 / f"{cid}.json"
            assert r["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
            assert r["split"] == s and r["source"] == "template_text" and r["parent_id"] == cid
            assert validate_doc("manifest", r) == []


def test_lock_lists_every_v2_test_file_and_no_dev_file(split_ids):
    locked = set(read_lock(LOCK_PATH))
    for cid in split_ids["test"]:
        assert f"data/gold_v2/{cid}.json" in locked
    for cid in split_ids["dev"]:
        assert f"data/gold_v2/{cid}.json" not in locked
    assert verify_lock(LOCK_PATH, ROOT) == []


def test_lock_only_gained_lines_since_the_v1_freeze():
    """APPEND-ONLY: every line of the committed v1 lock is still there, byte for byte, in order."""
    try:
        old = subprocess.run(
            ["git", "show", "a7ba312:data/splits/test.lock"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git history not available")
    new = LOCK_PATH.read_bytes().decode("utf-8")
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    it = iter(new_lines)
    assert all(any(x == y for y in it) for x in old_lines), "an old lock line changed or moved"
    added = [ln for ln in new_lines if ln not in set(old_lines)]
    assert added and all(
        re.match(r"^[0-9a-f]{64}  data/gold_v2/", ln) or ln.startswith("#") for ln in added
    )


def test_editing_a_v2_test_file_is_caught(tmp_path, split_ids):
    copy = tmp_path / "repo"
    (copy / "data" / "splits").mkdir(parents=True)
    shutil.copytree(V2, copy / "data" / "gold_v2")
    shutil.copy(LOCK_PATH, copy / "data" / "splits" / "test.lock")
    lock = copy / "data" / "splits" / "test.lock"
    # only the v2 lines matter here: drop every other locked path
    keep = [
        ln
        for ln in lock.read_text("utf-8").splitlines()
        if ln.startswith("#") or "data/gold_v2/" in ln
    ]
    lock.write_text("\n".join(keep) + "\n", encoding="utf-8")
    assert verify_lock(lock, copy) == []
    victim = copy / "data" / "gold_v2" / f"{split_ids['test'][0]}.json"
    old = victim.read_bytes()
    new = (
        old.replace(b'"has_negation": true', b'"has_negation": false', 1)
        if b'"has_negation": true' in old
        else old.replace(b'"has_negation": false', b'"has_negation": true', 1)
    )
    assert new != old
    victim.write_bytes(new)
    problems = verify_lock(lock, copy)
    assert len(problems) == 1 and "CHANGED" in problems[0]
