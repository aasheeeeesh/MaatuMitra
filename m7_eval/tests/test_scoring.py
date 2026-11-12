"""Record-vs-gold scoring by severity (docs/severity.md incl. the record.v2 mapping note)."""

import copy

from m7_eval import scoring


def span(s, e, t=0):
    return {"turn_index": t, "span_text": "x" * (e - s), "char_start": s, "char_end": e}


def ev(s, e):
    return {
        "span_text": "x" * (e - s),
        "char_start": s,
        "char_end": e,
        "audio_start": None,
        "audio_end": None,
    }


GOLD = {
    "conversation_id": "m1-a1-000",
    "template_family_id": "a_fever_cough__f1",
    "gold_record": {
        "patient_ref": "pt-1",
        "encounter_type": "physician_consult",
        "symptoms": [{"name": "cough", "present": False, "gold_span": span(0, 5)}],
        "medications": [
            {
                "drug": "amoxicillin",
                "dose_value": 500,
                "dose_unit": "mg",
                "frequency_per_day": 3,
                "duration_days": 5,
                "negated": False,
                "gold_span": span(10, 30),
            }
        ],
        "advice": [{"text": "drink water", "negated": False, "gold_span": span(40, 50)}],
        "follow_up": None,
    },
}


def rec_from_gold(g):
    gr = copy.deepcopy(g["gold_record"])
    r = {
        "schema_version": "record.v1",
        "symptoms": [],
        "medications": [],
        "advice": [],
        "follow_up": None,
    }
    for k in ("symptoms", "medications", "advice"):
        for it in gr[k]:
            sp = it.pop("gold_span")
            it.pop("gold_field_spans", None)
            it["evidence"] = ev(sp["char_start"], sp["char_end"])
            r[k].append(it)
    for k in ("patient_age_band", "weight_kg"):
        if k in gr:
            v = gr[k]
            if v is not None:
                v = {kk: vv for kk, vv in v.items() if kk != "gold_span"}
            r[k] = v
    return r


def codes(results):
    return sorted(r.code for r in results if r.code)


def test_perfect_record_has_no_errors_and_m3_field_count():
    res = scoring.score_record(rec_from_gold(GOLD), GOLD)
    assert codes(res) == []
    # medication 6 + symptom 2 + advice 2 + follow-up 1 = 11 fields (same unit as m3_extract)
    assert len(res) == 11


def test_negation_flip_dose_and_frequency_errors():
    r = rec_from_gold(GOLD)
    r["symptoms"][0]["present"] = True
    r["medications"][0]["dose_value"] = 50
    r["medications"][0]["frequency_per_day"] = 2
    assert codes(scoring.score_record(r, GOLD)) == ["CR-DOSE", "CR-FREQ", "CR-NEG"]


def test_wrong_drug_with_overlapping_evidence_is_cr_drug():
    r = rec_from_gold(GOLD)
    r["medications"][0]["drug"] = "azithromycin"
    assert codes(scoring.score_record(r, GOLD)) == ["CR-DRUG"]


def test_missed_and_unsupported_drug():
    r = rec_from_gold(GOLD)
    r["medications"][0]["evidence"] = ev(60, 70)
    r["medications"][0]["drug"] = "azithromycin"  # no overlap -> missed + unsupported
    assert codes(scoring.score_record(r, GOLD)) == ["CR-UNSUPPORTED", "MA-MISSED-DRUG"]


def test_missing_record_counts_items_once():
    res = scoring.score_record(None, GOLD)
    assert codes(res) == ["MA-MISSED-ADVICE", "MA-MISSED-DRUG", "MA-MISSED-SYMPTOM"]


def test_v1_reports_new_classes_as_not_measurable():
    assert scoring.measurable_v2(rec_from_gold(GOLD), GOLD) is False
    s = scoring.summarise(
        [("a_fever_cough__f1", scoring.score_record(rec_from_gold(GOLD), GOLD))], v2=False
    )
    assert s["not_measurable"] == ["CR-LIQUID-STRENGTH", "CR-PAEDIATRIC", "CR-ROUTE"]


GOLD2 = copy.deepcopy(GOLD)
GOLD2["schema_version"] = "gold.v2"
GOLD2["gold_record"]["patient_age_band"] = {"band": "child", "gold_span": span(0, 3)}
GOLD2["gold_record"]["weight_kg"] = None
GOLD2["gold_record"]["medications"][0].update(
    {
        "dose_value": 5,
        "dose_unit": "ml",
        "route": "oral",
        "strength_value": 125,
        "strength_unit": "mg/5ml",
        "formulation": "syrup",
        "as_needed": False,
        "food_timing": "after_food",
        "status": "prescribed",
        "speaker": "doctor",
    }
)


def rec2():
    r = rec_from_gold(GOLD2)
    r["schema_version"] = "record.v2"
    return r


def test_v2_perfect_and_field_count():
    res = scoring.score_record(rec2(), GOLD2)
    assert codes(res) == []
    # v1 11 + 7 new medication fields + age band + weight = 20
    assert len(res) == 20
    assert scoring.measurable_v2(rec2(), GOLD2) is True


def test_v2_route_strength_paediatric_status():
    r = rec2()
    m = r["medications"][0]
    m["route"] = "im"
    m["strength_value"] = 250
    m["status"] = "not_taken"
    m["food_timing"] = None
    r["patient_age_band"] = {"band": "adult"}
    assert codes(scoring.score_record(r, GOLD2)) == [
        "CR-LIQUID-STRENGTH",
        "CR-NEG",
        "CR-PAEDIATRIC",
        "CR-ROUTE",
        "MA-MED-ATTRIBUTE",
    ]


def test_v2_missing_strength_for_ml_dose_and_injection_formulation():
    r = rec2()
    r["medications"][0]["strength_value"] = None
    r["medications"][0]["strength_unit"] = None
    r["medications"][0]["formulation"] = "injection"
    r["medications"][0]["status"] = "already_taken"  # given vs given -> MAJOR only
    assert codes(scoring.score_record(r, GOLD2)) == ["CR-LIQUID-STRENGTH", "CR-ROUTE", "MA-STATUS"]


def test_summary_rates_and_prf():
    r = rec_from_gold(GOLD)
    r["symptoms"].append({"name": "fever", "present": True, "evidence": ev(80, 84)})
    per = [
        ("a_fever_cough__f1", scoring.score_record(r, GOLD)),
        ("a_fever_cough__f2", scoring.score_record(None, GOLD)),
    ]
    s = scoring.summarise(per, v2=False, seed=1)
    crit = s["severity"]["critical"]
    assert crit["errors"] == 0 and crit["n_fields"] == 23
    maj = s["severity"]["major"]
    assert maj["errors"] == 4  # extra symptom + 3 missed items
    sym = s["items"]["symptom"]
    assert (sym["tp"], sym["fp"], sym["fn"]) == (1, 1, 1)
    assert sym["precision"] == 0.5 and sym["recall"] == 0.5
    assert maj["cluster_lo_per_1000"] is not None
