"""MOCK MODE: build a tiny fake repository tree from fixtures/ so every m7 experiment (E1-E6)
can run without real module outputs. The fake m2/m4/m5/m8 outputs are SYNTHETIC test inputs
(made here, deterministic); numbers from a mock run mean nothing.

Fake split: dev = fx-asha-001, fx-asha-002, fx-pharm-003, fx-phys-004; test = fx-nurse-005,
fx-trap-006 (so the guard has real test ids to refuse).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

DEV = ["fx-asha-001", "fx-asha-002", "fx-pharm-003", "fx-phys-004"]
TEST = ["fx-nurse-005", "fx-trap-006"]

TEMPLATES = """\
category: x
families:
  - id: a_fever_cough_duration
    templates:
      - id: x1
        turns:
          - {role: asha, text: "[[s1|{S1.kn}]] ಎಷ್ಟು ದಿನದಿಂದ ಇದೆ?"}
          - {role: caregiver, text: "{X1}"}
  - id: f_nurse_multi_symptom
    templates:
      - id: x2
        turns:
          - {role: nurse, text: "[[s1|{S1.kn}]] ಎಷ್ಟು ದಿನದಿಂದ ಇದೆ?"}
          - {role: patient, text: "ಹೊಸ ವಾಕ್ಯ [[s2|{S2.kn}]]."}
"""


def _w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _jsonl(p: Path, rows: list[dict]) -> None:
    _w(p, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def build_mock_root(repo: Path, dst: Path) -> Path:
    fx = repo / "fixtures"
    for d in ("m7_eval/configs",):
        shutil.copytree(repo / d, dst / d, dirs_exist_ok=True)
    neg = repo / ".claude/skills/kannada-nlp/negation_table.yaml"
    if neg.exists():
        _w(dst / ".claude/skills/kannada-nlp/negation_table.yaml", neg.read_text(encoding="utf-8"))
    lex_csv = fx / "lexicon" / "drugs_fixture.csv"
    if lex_csv.exists():
        _w(dst / "data/lexicon/drugs.csv", lex_csv.read_text(encoding="utf-8"))
    sp = dst / "data/splits"
    _w(sp / "dev.txt", "\n".join(DEV) + "\n")
    _w(sp / "test.txt", "\n".join(TEST) + "\n")
    lock = ["# FAKE test lock (mock)"]
    gold = {}
    for cid in DEV + TEST:
        g = json.loads((fx / "gold/valid" / f"{cid}.json").read_text(encoding="utf-8"))
        gold[cid] = g
        gp = dst / "data/gold" / f"{cid}.json"
        _w(gp, json.dumps(g, ensure_ascii=False, indent=1))
        tp = fx / "transcript/valid" / f"{cid}__gold.json"
        _w(dst / "data/transcripts/gold" / f"{cid}__gold.json", tp.read_text(encoding="utf-8"))
        rp = fx / "record/valid" / f"rec-{cid}.json"
        _w(dst / "results/m3_extract/rules" / f"rules-{cid}.json", rp.read_text(encoding="utf-8"))
        if cid in TEST:
            for rel in (f"data/gold/{cid}.json", f"data/transcripts/gold/{cid}__gold.json"):
                h = hashlib.sha256((dst / rel).read_bytes()).hexdigest()
                lock.append(f"{h}  {rel}")
    _w(sp / "test.lock", "\n".join(lock) + "\n")
    fams = {
        s: sorted({gold[c]["template_family_id"] for c in ids})
        for s, ids in (("dev", DEV), ("test", TEST))
    }
    _w(sp / "split_plan.json", json.dumps({"families": fams}, indent=1))
    _w(dst / "data/templates/x_mock.yaml", TEMPLATES)
    _w(dst / "results/m3_extract/llm_subset.txt", "\n".join(DEV[:3]) + "\n")
    _w(
        dst / "results/m3_extract/llm_STALE_pre_refreeze/run_summary.json",
        json.dumps({"model": "mock-llm", "n": 3, "latency_ms_p50": 1.0, "latency_ms_p95": 2.0}),
    )
    # ---- fake m2 (two runs, same dev utterances; the candidate drops one character)
    for run, drop in (("faster-whisper-small-int8", 0), ("candidate-model", 1)):
        rows = []
        for cid in DEV:
            text = json.loads(
                (dst / f"data/transcripts/gold/{cid}__gold.json").read_text(encoding="utf-8")
            )["text"]
            hyp = text[: len(text) - 3 * drop] if drop else text.replace(" ", "  ", 1)
            for variant in ("clean", "white_snr10"):
                rows.append(
                    {
                        "schema_version": "transcript.v1",
                        "audio_id": f"{cid}__mms_kan_base__{variant}",
                        "source": "tts",
                        "model": {"name": run, "revision": "mock"},
                        "text": hyp,
                        "words": [],
                        "latency_ms": 500 + 100 * drop,
                        "audio_duration_s": 5.0,
                        "hardware": "mock",
                        "created_at": "2026-11-12T00:00:00Z",
                    }
                )
        _jsonl(dst / "results/m2_asr" / run / "dev/transcripts.jsonl", rows)
    # ---- fake m4 E4 outputs
    e4 = dst / "results/m4_verify/dev/e4"
    res, logs = [], {"record": [], "transcript": []}
    n = 0
    for cid in DEV:
        for typ, tname, chk in (
            ("a", "negation drop", "C3"),
            ("f", "drug swap (confusable)", "C2"),
        ):
            for lv, cond in (("record", "with_encounter_index"), ("transcript", "text_only")):
                n += 1
                iid = f"E4-{lv[0].upper()}-{typ}-{n:04d}"
                caught = lv == "record" or (typ == "a" and cid != "fx-asha-002")
                res.append(
                    {
                        "id": iid,
                        "level": lv,
                        "condition": cond,
                        "type": typ,
                        "unique_key": f"{cid}|{typ}|{lv}",
                        "field": "present" if typ == "a" else "drug",
                        "field_path": "/symptoms/0/present"
                        if typ == "a"
                        else "/medications/0/drug",
                        "caught_at_field": caught,
                        "detected_at_field": caught,
                        "sent_to_review": True,
                        "at_field_checks": [chk] if caught else [],
                        "detected_checks": [chk] if caught else [],
                        "flagged_checks": [chk] if caught else ["C4"],
                    }
                )
                logs[lv].append(
                    {
                        "id": iid,
                        "source_id": cid,
                        "type": typ,
                        "type_name": tname,
                        "note": "mock edit",
                        "before": False,
                        "after": True,
                        "level": lv,
                    }
                )
    _jsonl(e4 / "injection_results.jsonl", res)
    for lv, rows in logs.items():
        _jsonl(e4 / f"injection_log_{lv}.jsonl", rows)
    _jsonl(
        e4 / "clean_flagged_fields.jsonl",
        [
            {
                "field": "/medications/0",
                "flags": ["C4: cannot_verify:count_unit [CR-DOSE]: mock"],
                "record_id": "rec-fx-pharm-003",
            },
            {
                "field": "/symptoms/1",
                "flags": ["C2: symptom 'chills' unknown", "C6: unknown"],
                "record_id": "rec-fx-asha-001",
            },
        ],
    )
    _w(
        e4 / "clean_flag_rate.csv",
        "unit,n,flagged,rate,wilson_lo,wilson_hi,flagged_excl_cannot_verify,rate_excl_cannot_verify,excl_wilson_lo,excl_wilson_hi\n"
        "record,4,2,0.5,0,1,1,0.25,0,1\nfield,20,2,0.1,0,1,1,0.05,0,1\n",
    )
    # ---- fake m5 and m8
    m5 = []
    for i in range(12):
        exp = "deny" if i % 3 else "allow"
        m5.append(
            {
                "case": {
                    "case_id": f"c{i}",
                    "role": "asha",
                    "attack": None if i % 2 else "sqli",
                    "expected": exp,
                },
                "layer": "db",
                "observed": exp,
                "outcome": "pass",
            }
        )
    _jsonl(dst / "results/m5_backend/access_matrix_results.jsonl", m5)
    for name in ("tfidf", "ollama"):
        rows = []
        for i, (split, kind) in enumerate(
            [
                ("dev", "answer"),
                ("dev", "answer"),
                ("dev", "oos"),
                ("dev", "unsafe"),
                ("test", "answer"),
            ]
        ):
            ok = i != 1
            rows.append(
                {
                    "id": f"q{i}",
                    "split": split,
                    "topic": "amr",
                    "kind": kind,
                    "lang": "en",
                    "q": f"mock question {i}",
                    "expected_card": "card-a" if kind == "answer" else None,
                    "pred_abstain": kind != "answer" or not ok,
                    "pred_card": "card-a" if kind == "answer" and ok else None,
                    "reason": "mock",
                    "score": 0.5,
                }
            )
        _jsonl(dst / f"results/m8_helper/predictions_{name}.jsonl", rows)
    return dst
