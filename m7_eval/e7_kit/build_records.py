"""Build the E7 user-study materials from DEV gold (synthetic, template-generated; no patient).

    uv run python -m m7_eval.e7_kit.build_records

Writes into m7_eval/e7_kit/: records/e7-rNN.json (20 record.v1 documents, 10 with ONE planted
critical error each), packets/e7-rNN.md (conversation + record table for the reviewer),
answer_key.csv (facilitator only), design.csv (12 participants, within-subject, flags shown vs
hidden in counterbalanced blocks, order randomised with a fixed seed).

The "verifier flags" shown to participants are SIMULATED on purpose: 7 of 10 planted errors are
flagged, 3 are not, and 2 of 10 clean records carry a false flag, so over-trust in the flags
(automation bias) can be seen. This is a study design choice, not m4 output.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import random
import sys
from pathlib import Path

from m7_eval.guard import SplitGuard

SEED = 20261109
N_PARTICIPANTS = 12
KIT = Path(__file__).resolve().parent
MUTATIONS = ("CR-DOSE", "CR-FREQ", "CR-DUR", "CR-DRUG", "CR-NEG")
MISSED = {2, 5, 8}  # planted-error records whose simulated flag is withheld
FALSE_FLAG = {1, 6}  # clean records that get a simulated false flag
SWAP = {"amoxicillin": "azithromycin", "azithromycin": "amoxicillin"}


def _ev(span: dict) -> dict:
    return {
        "span_text": span["span_text"],
        "char_start": span["char_start"],
        "char_end": span["char_end"],
        "audio_start": None,
        "audio_end": None,
    }


def gold_to_record(gold: dict, rid: str) -> dict:
    gr = copy.deepcopy(gold["gold_record"])
    rec = {
        "schema_version": "record.v1",
        "record_id": rid,
        "patient_ref": gr["patient_ref"],
        "encounter_type": gr["encounter_type"],
        "source_transcript_id": gold["conversation_id"],
        "extractor": {"name": "e7-kit-synthetic", "version": "1"},
        "status": "draft",
        "symptoms": [],
        "medications": [],
        "advice": [],
        "follow_up": None,
    }
    for k in ("symptoms", "medications", "advice"):
        for it in gr[k]:
            sp = it.pop("gold_span")
            rec[k].append({**it, "evidence": _ev(sp)})
    if gr.get("follow_up"):
        rec["follow_up"] = {
            "text": gr["follow_up"]["text"],
            "evidence": _ev(gr["follow_up"]["gold_span"]),
        }
    return rec


def _mutate(rec: dict, code: str) -> tuple[str, object, object]:
    m = rec["medications"][0]
    if code == "CR-DOSE":
        before = m["dose_value"]
        m["dose_value"] = before * 10 if before < 100 else before / 10
        return "/medications/0/dose_value", before, m["dose_value"]
    if code == "CR-FREQ":
        before = m["frequency_per_day"]
        m["frequency_per_day"] = 1 if before != 1 else 3
        return "/medications/0/frequency_per_day", before, m["frequency_per_day"]
    if code == "CR-DUR":
        before = m["duration_days"]
        m["duration_days"] = before + 2
        return "/medications/0/duration_days", before, m["duration_days"]
    if code == "CR-DRUG":
        before = m["drug"]
        m["drug"] = SWAP.get(before, "amoxicillin")
        return "/medications/0/drug", before, m["drug"]
    before = m["negated"]
    m["negated"] = not before
    return "/medications/0/negated", before, m["negated"]


def _eligible(g: dict) -> bool:
    meds = g["gold_record"]["medications"]
    return bool(meds) and all(
        meds[0].get(f) is not None for f in ("dose_value", "frequency_per_day", "duration_days")
    )


def _packet(rid: str, gold: dict, rec: dict) -> str:
    s = f"# Review packet {rid}\n\nSYNTHETIC conversation (template-generated, not native-validated; no real patient).\n\n"
    s += "## Conversation\n\n" + "".join(
        f"{i + 1}. **{t['speaker_role']}**: {t['text']}\n" for i, t in enumerate(gold["turns"])
    )
    s += "\n## Draft record (check every value against the conversation)\n\n| field | value |\n|---|---|\n"
    s += f"| encounter | {rec['encounter_type']} |\n"
    for i, x in enumerate(rec["symptoms"]):
        s += f"| symptom {i + 1} | {x['name']} ({'present' if x['present'] else 'absent'}) |\n"
    for i, m in enumerate(rec["medications"]):
        s += (
            f"| medicine {i + 1} | {m['drug']}, {m['dose_value']} {m['dose_unit']}, "
            f"{m['frequency_per_day']}/day, {m['duration_days']} days"
            f"{', NEGATED' if m['negated'] else ''} |\n"
        )
    for i, a in enumerate(rec["advice"]):
        s += f"| advice {i + 1} | {a['text']}{' (negated)' if a['negated'] else ''} |\n"
    s += "\n## Verifier flags\n\nShown ONLY in the flags_shown condition (facilitator reads simulated_flag from answer_key.csv).\n"
    return s


def build(root: Path, out: Path = KIT) -> dict[str, str]:
    """Write the kit into `out`; return {relative path: sha256} of written files."""
    g = SplitGuard(root, "dev")
    golds = [g.read_json(f"data/gold/{c}.json") for c in sorted(g.ids)]
    rng = random.Random(SEED)  # noqa: S311 (study design, not security)
    eligible = [x for x in golds if _eligible(x)]
    other = [x for x in golds if not _eligible(x) and x["gold_record"]["medications"]]
    picked_err = rng.sample(eligible, 10)
    rest = [x for x in eligible + other if x not in picked_err]
    picked_clean = rng.sample(rest, 10)
    written: dict[str, str] = {}

    def w(rel: str, text: str) -> None:
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        written[rel] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    key = []
    items = [(x, True, i) for i, x in enumerate(picked_err)] + [
        (x, False, i) for i, x in enumerate(picked_clean)
    ]
    order = list(range(20))
    rng.shuffle(order)  # record ids do not reveal which records carry errors
    for n, idx in enumerate(order, 1):
        gold, has_err, i = items[idx]
        rid = f"e7-r{n:02d}"
        rec = gold_to_record(gold, rid)
        row = {
            "record_id": rid,
            "has_planted_error": "yes" if has_err else "no",
            "error_code": "",
            "error_field": "",
            "before": "",
            "after": "",
            "simulated_flag": "no",
            "source_conversation": gold["conversation_id"],
            "set": "A" if i < 5 else "B",
        }
        if has_err:
            code = MUTATIONS[i % len(MUTATIONS)]
            path, before, after = _mutate(rec, code)
            row.update(
                error_code=code,
                error_field=path,
                before=before,
                after=after,
                simulated_flag="no" if i in MISSED else "yes",
            )
        elif i in FALSE_FLAG:
            row.update(simulated_flag="yes", error_field="/medications/0/dose_value (false alarm)")
        key.append(row)
        w(f"records/{rid}.json", json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        w(f"packets/{rid}.md", _packet(rid, gold, rec))
    buf = io.StringIO()
    cw = csv.DictWriter(buf, fieldnames=list(key[0]), lineterminator="\n")
    cw.writeheader()
    cw.writerows(sorted(key, key=lambda r: r["record_id"]))
    w("answer_key.csv", buf.getvalue())
    # design: block A/B gets flags in alternating participants; block order alternates too
    sets = {s: [r["record_id"] for r in key if r["set"] == s] for s in ("A", "B")}
    drows = []
    for p in range(1, N_PARTICIPANTS + 1):
        shown = "A" if p % 2 else "B"
        blocks = [
            ("flags_shown", sets[shown]),
            ("flags_hidden", sets["B" if shown == "A" else "A"]),
        ]
        if (p - 1) // 2 % 2:
            blocks.reverse()
        pos = 0
        for cond, ids in blocks:
            ids = sorted(ids)
            rng.shuffle(ids)
            for rid in ids:
                pos += 1
                drows.append(
                    {
                        "participant_id": f"P{p:02d}",
                        "position": pos,
                        "record_id": rid,
                        "condition": cond,
                    }
                )
    buf = io.StringIO()
    cw = csv.DictWriter(buf, fieldnames=list(drows[0]), lineterminator="\n")
    cw.writeheader()
    cw.writerows(drows)
    w("design.csv", buf.getvalue())
    sheet = "participant_id,record_id,condition,position,review_seconds,marked_error,marked_field,notes\n"
    sheet += "".join(
        f"{r['participant_id']},{r['record_id']},{r['condition']},{r['position']},,,,\n"
        for r in drows
    )
    w("record_sheet.csv", sheet)
    return written


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    print(f"wrote {len(build(root))} files into {KIT}", file=sys.stdout)
