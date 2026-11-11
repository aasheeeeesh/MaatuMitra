"""COMPARISON pipeline (E2): a local open LLM through Ollama (127.0.0.1 only).

Model: qwen3:4b-instruct (Q4_K_M, 4.0B, Apache-2.0 per `ollama show`), revision = Ollama digest
below. temperature 0, fixed seed, JSON-schema-constrained output (Ollama `format`).
The model returns QUOTES, never offsets: our code finds each quote verbatim in the transcript and
then runs the same evidence check as the rules pipeline. Any quote that is not verbatim rejects
the whole record. We never trust the model's claim that it quoted correctly.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from contracts.validate import validate_doc
from m3_extract.evidence import check_evidence, evidence_for, locate_quote
from m3_extract.lexicon import DrugLexicon
from m3_extract.rules import _default_lexicon, load_symptoms
from m3_extract.textnorm import check_stored

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen3:4b-instruct"
EXPECTED_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
SEED = 20261110
PROMPT_VERSION = "prompt-v1"
UNITS = ["mg", "g", "mcg", "ml", "tablet", "capsule", "sachet", "drop", "teaspoon", "IU"]
FIX = Path(__file__).resolve().parents[1] / "fixtures"
FEWSHOT_IDS = ("fx-pharm-003", "fx-asha-002", "fx-nurse-005")

Generate = Callable[[dict[str, Any], dict[str, Any]], tuple[str, dict[str, Any]]]


def output_schema(lexicon: DrugLexicon) -> dict[str, Any]:
    sym_names = sorted(set(load_symptoms().values()))
    q = {
        "type": "string",
        "description": "exact copy of the words in the transcript that support this item",
    }
    num = {"type": ["number", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["symptoms", "medications", "advice", "follow_up"],
        "properties": {
            "symptoms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "present", "quote"],
                    "properties": {
                        "name": {"enum": sym_names},
                        "present": {"type": "boolean"},
                        "quote": q,
                    },
                },
            },
            "medications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "drug",
                        "dose_value",
                        "dose_unit",
                        "frequency_per_day",
                        "duration_days",
                        "negated",
                        "quote",
                    ],
                    "properties": {
                        "drug": {"enum": sorted(set(lexicon.generics))},
                        "dose_value": num,
                        "dose_unit": {"enum": [*UNITS, None]},
                        "frequency_per_day": num,
                        "duration_days": num,
                        "negated": {"type": "boolean"},
                        "quote": q,
                    },
                },
            },
            "advice": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["text", "negated", "quote"],
                    "properties": {
                        "text": {"type": "string"},
                        "negated": {"type": "boolean"},
                        "quote": q,
                    },
                },
            },
            "follow_up": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["text", "quote"],
                        "properties": {"text": {"type": "string"}, "quote": q},
                    },
                ]
            },
        },
    }


def _lexicon_lines(lexicon: DrugLexicon) -> str:
    by: dict[str, list[str]] = {}
    for form, (g, _mt) in lexicon.forms.items():
        by.setdefault(g, []).append(" ".join(form))
    return "\n".join(f"- {g}: {', '.join(sorted(set(v)))}" for g, v in sorted(by.items()))


def _symptom_lines() -> str:
    by: dict[str, list[str]] = {}
    for form, name in load_symptoms().items():
        by.setdefault(name, []).append(" ".join(form))
    return "\n".join(f"- {n}: {', '.join(v)}" for n, v in sorted(by.items()))


def _fewshot() -> str:
    parts = []
    for cid in FEWSHOT_IDS:
        g = json.loads((FIX / "gold" / "valid" / f"{cid}.json").read_text(encoding="utf-8"))
        gr = g["gold_record"]

        def strip(items, keys):
            return [
                {**{k: it[k] for k in keys}, "quote": it["gold_span"]["span_text"]} for it in items
            ]

        out = {
            "symptoms": strip(gr["symptoms"], ["name", "present"]),
            "medications": strip(
                gr["medications"],
                [
                    "drug",
                    "dose_value",
                    "dose_unit",
                    "frequency_per_day",
                    "duration_days",
                    "negated",
                ],
            ),
            "advice": strip(gr["advice"], ["text", "negated"]),
            "follow_up": None
            if gr["follow_up"] is None
            else {
                "text": gr["follow_up"]["text"],
                "quote": gr["follow_up"]["gold_span"]["span_text"],
            },
        }
        text = "\n".join(t["text"] for t in g["turns"])
        parts.append(f"TRANSCRIPT:\n{text}\nJSON:\n{json.dumps(out, ensure_ascii=False)}")
    return "\n\n".join(parts)


SYSTEM = """You extract a structured clinical record from a short Kannada (sometimes code-switched English) conversation transcript. All data is synthetic. Output JSON only, matching the schema.

Rules:
- Only include items that were actually spoken. Do not invent drugs, doses, numbers or symptoms.
- "quote": copy the supporting words EXACTLY from the transcript (same script, same spelling, contiguous, from one line). Never paraphrase or translate a quote.
- medications: "drug" is the English generic name from the drug list. dose_value + dose_unit is the amount per dose as spoken (500 mg -> 500, "mg"; ಒಂದು ಮಾತ್ರೆ -> 1, "tablet"; ಕ್ಯಾಪ್ಸೂಲ್ -> "capsule"). frequency_per_day from "ದಿನಕ್ಕೆ N ಬಾರಿ/ಸಾರಿ". duration_days from "N ದಿನ/ದಿವಸ" (ಒಂದು ವಾರ = 7). Use null when not spoken. Kannada digits ೦-೯ are numbers. One entry per drug.
- negated=true when the drug is refused, not taken, not to be taken, "this is not X" (ಅಲ್ಲ), or not taken (ತೆಗೆದುಕೊಳ್ಳದೆ).
- symptoms: "name" from the symptom list; present=false when denied (ಇಲ್ಲ, ಇಲ್ಲಾ, ಆಗಿಲ್ಲ, ಯಾವುದೇ ... ಇಲ್ಲ).
- If a turn is only "ಇಲ್ಲ."/"ಇಲ್ಲಾ." it answers the previous question: the item asked about is negated/absent; "ಹೌದು." means yes. Quote the item from the QUESTION line.
- Do not treat these as negation: ಎಲ್ಲ, ಎಲ್ಲಾ (all), ಇಲ್ಲಿ (here), ಅಲ್ಲಿ (there), ಅಲ್ವಾ/ಅಲ್ವ (right?), ಮಾತ್ರ (only), ಮಾತ್ರೆ (tablet), ಇದೆ, ಬಂದಿದೆ, ಇದ್ದರೆ.
- advice: short lower-case English gloss of each instruction that is not a medication dose (for example "take after food", "finish all tablets"); prohibitions get negated=true and a text starting "do not".
- follow_up: one English gloss of a "come back / come if ..." instruction, else null.
- A symptom mentioned only inside an "if ..." condition is not a symptom of the patient.

DRUG LIST (generic name: spoken forms):
{drugs}

SYMPTOM LIST (name: spoken forms):
{symptoms}

EXAMPLES:
{examples}"""


def request_body(text: str, schema: dict[str, Any], lexicon: DrugLexicon) -> dict[str, Any]:
    system = SYSTEM.format(
        drugs=_lexicon_lines(lexicon), symptoms=_symptom_lines(), examples=_fewshot()
    )
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"TRANSCRIPT:\n{text}\nJSON:"},
        ],
        "format": schema,
        "stream": False,
        "think": False,
        "keep_alive": "15m",
        "options": {
            "temperature": 0,
            "seed": SEED,
            "num_ctx": 8192,
            "num_predict": 1536,
            "top_k": 1,
        },
    }


def ollama_generate(body: dict[str, Any], timeout_s: float = 600.0) -> tuple[str, dict[str, Any]]:
    with httpx.Client(timeout=timeout_s) as c:
        r = c.post(f"{OLLAMA_URL}/api/chat", json=body)
        r.raise_for_status()
        d = r.json()
    meta = {
        k: d.get(k)
        for k in (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "eval_count",
            "eval_duration",
        )
    }
    return d["message"]["content"], meta


def model_digest() -> str | None:
    try:
        with httpx.Client(timeout=10) as c:
            tags = c.get(f"{OLLAMA_URL}/api/tags").json()
    except httpx.HTTPError:
        return None
    for m in tags.get("models", []):
        if m.get("name") == MODEL or m.get("model") == MODEL:
            return m.get("digest")
    return None


@dataclass
class LLMResult:
    record: dict[str, Any]
    rejected_reasons: list[str]
    raw: str
    latency_ms: float
    meta: dict[str, Any] = field(default_factory=dict)


def extract_llm(
    transcript: dict[str, Any],
    context: dict[str, Any],
    *,
    lexicon: DrugLexicon | None = None,
    generate: Callable[[dict[str, Any], dict[str, Any]], tuple[str, dict[str, Any]]] | None = None,
    record_id: str | None = None,
    digest: str = EXPECTED_DIGEST,
) -> LLMResult:
    lexicon = lexicon or _default_lexicon()
    text = transcript["text"]
    check_stored(text)
    schema = output_schema(lexicon)
    body = request_body(text, schema, lexicon)
    t0 = time.perf_counter()
    if generate is None:
        raw, meta = ollama_generate(body)
    else:
        raw, meta = generate(body, schema)
    latency = 1000 * (time.perf_counter() - t0)
    rid = record_id or f"llm-{transcript['audio_id']}"
    record: dict[str, Any] = {
        "schema_version": "record.v1",
        "record_id": rid,
        "patient_ref": context["patient_ref"],
        "encounter_type": context["encounter_type"],
        "source_transcript_id": transcript["audio_id"],
        "extractor": {
            "name": f"llm-{MODEL}",
            "version": f"ollama-{digest[:12]}+{PROMPT_VERSION}+seed{SEED}",
        },
        "status": "draft",
        "symptoms": [],
        "medications": [],
        "advice": [],
        "follow_up": None,
    }
    reasons: list[str] = []
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        return LLMResult(record, [f"model output is not valid JSON: {e}"], raw, latency, meta)

    def ev(path: str, quote: Any) -> dict[str, Any]:
        loc = locate_quote(text, quote if isinstance(quote, str) else "")
        if loc is None:
            reasons.append(f"{path}: quote not found verbatim in transcript: {quote!r}")
            # keep the claim for inspection; this record will be rejected
            return {
                "span_text": str(quote) or "?",
                "char_start": 0,
                "char_end": max(1, len(str(quote))),
                "audio_start": None,
                "audio_end": None,
            }
        return evidence_for(transcript, *loc)

    try:
        for i, s in enumerate(out["symptoms"]):
            record["symptoms"].append(
                {
                    "name": s["name"],
                    "present": s["present"],
                    "evidence": ev(f"symptoms/{i}", s.get("quote")),
                }
            )
        for i, m in enumerate(out["medications"]):
            record["medications"].append(
                {
                    **{
                        k: m[k]
                        for k in (
                            "drug",
                            "dose_value",
                            "dose_unit",
                            "frequency_per_day",
                            "duration_days",
                            "negated",
                        )
                    },
                    "evidence": ev(f"medications/{i}", m.get("quote")),
                }
            )
        for i, a in enumerate(out["advice"]):
            record["advice"].append(
                {
                    "text": a["text"],
                    "negated": a["negated"],
                    "evidence": ev(f"advice/{i}", a.get("quote")),
                }
            )
        fu = out.get("follow_up")
        if fu:
            record["follow_up"] = {"text": fu["text"], "evidence": ev("follow_up", fu.get("quote"))}
    except (KeyError, TypeError, AttributeError) as e:
        reasons.append(f"model output malformed: {type(e).__name__}: {e}")
    reasons += [f"record.v1: {e}" for e in validate_doc("record.v1", record)]
    if not reasons:
        reasons += check_evidence(record, text)
    return LLMResult(record, reasons, raw, latency, meta)
