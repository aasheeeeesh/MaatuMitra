"""LLM pipeline without a model: a fake generate() stands in for Ollama.

The point: offsets are ALWAYS recomputed by our code from the model's quote; a quote that is not
in the transcript fails the evidence check and the record is rejected.
"""

import json

from jsonschema import Draft202012Validator

from contracts.validate import validate_doc
from m3_extract import llm
from m3_extract.tests._helpers import CTX, FIX, load_json


def fake(payload):
    def generate(prompt, schema):
        return json.dumps(payload, ensure_ascii=False), {"eval_count": 1}

    return generate


TR = load_json(FIX / "transcript" / "valid" / "fx-pharm-003__gold.json")
GOOD = {
    "symptoms": [],
    "medications": [
        {
            "drug": "amoxicillin",
            "dose_value": 500,
            "dose_unit": "mg",
            "frequency_per_day": 3,
            "duration_days": 5,
            "negated": False,
            "quote": "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ",
        }
    ],
    "advice": [{"text": "take after food", "negated": False, "quote": "ಊಟದ ನಂತರ"}],
    "follow_up": None,
}


def test_output_schema_is_valid_json_schema(fx_lexicon):
    schema = llm.output_schema(fx_lexicon)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(GOOD)


def test_good_output_becomes_valid_record_with_our_offsets(fx_lexicon):
    res = llm.extract_llm(TR, CTX, lexicon=fx_lexicon, generate=fake(GOOD))
    assert res.rejected_reasons == []
    rec = res.record
    assert validate_doc("record.v1", rec) == []
    ev = rec["medications"][0]["evidence"]
    assert TR["text"][ev["char_start"] : ev["char_end"]] == ev["span_text"]
    assert rec["extractor"]["name"].startswith("llm-")


def test_forged_quote_rejects_whole_record(fx_lexicon):
    bad = json.loads(json.dumps(GOOD))
    bad["medications"][0]["quote"] = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 250 mg"  # never said
    res = llm.extract_llm(TR, CTX, lexicon=fx_lexicon, generate=fake(bad))
    assert res.rejected_reasons
    assert any("medications/0" in r for r in res.rejected_reasons)


def test_model_offsets_are_ignored(fx_lexicon):
    bad = json.loads(json.dumps(GOOD))
    bad["medications"][0]["char_start"] = 999  # extra keys from a model are never trusted
    res = llm.extract_llm(TR, CTX, lexicon=fx_lexicon, generate=fake(bad))
    ev = res.record["medications"][0]["evidence"]
    assert ev["char_start"] == 0


def test_unparseable_output_is_rejected(fx_lexicon):
    def generate(prompt, schema):
        return "not json {", {}

    res = llm.extract_llm(TR, CTX, lexicon=fx_lexicon, generate=generate)
    assert res.rejected_reasons and "json" in res.rejected_reasons[0].lower()


def test_schema_violation_is_rejected(fx_lexicon):
    bad = json.loads(json.dumps(GOOD))
    bad["medications"][0]["dose_value"] = -5
    res = llm.extract_llm(TR, CTX, lexicon=fx_lexicon, generate=fake(bad))
    assert res.rejected_reasons


def test_request_body_is_deterministic_and_local(fx_lexicon):
    body = llm.request_body("ಜ್ವರ ಇದೆ.", llm.output_schema(fx_lexicon), fx_lexicon)
    assert body["options"]["temperature"] == 0
    assert body["options"]["seed"] == llm.SEED
    assert body["format"]["type"] == "object"
    assert body["stream"] is False
    assert llm.OLLAMA_URL.startswith("http://127.0.0.1:")
