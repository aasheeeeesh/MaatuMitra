"""Convert record.v1 -> record.v2 and gold.v1 -> gold.v2 (a CONTRACT TOOL, importable by any module).

Usage (from the repo root):
    uv run python -m contracts.migrate_v1_to_v2 record <in.json|in.jsonl> [-o out]
    uv run python -m contracts.migrate_v1_to_v2 gold   <in.json|in.jsonl> [-o out]

Without -o the result is printed (one JSON document per line). Exit code 0 = all converted,
1 = an input document is not a valid v1 document (nothing is written), 2 = usage error.

The conversion is deliberately CONSERVATIVE (it never invents clinical meaning):
  * every new medication field is null: route, strength_value, strength_unit, formulation,
    as_needed, food_timing; field_evidence / gold_field_spans = {}
  * medications[].status = "unknown" for EVERY row. In particular negated: true does NOT become
    "advised_against": in v1 it could also mean "not taken" or "course not finished" (D-122,
    finding M3-M1), so guessing would create a wrong clinical claim.
  * negated is copied unchanged (in v2 it keeps only its sentence-level meaning)
  * record: speaker = "unknown" (transcript.v1 has no speaker roles)
  * gold: speaker = role of the turn of the main gold_span (physician -> doctor); this is exact
  * patient_age_band = null, weight_kg = null
A migrated document is valid record.v2 / gold.v2, but it has NO route, strength or age
information, so the CR-ROUTE / CR-PAEDIATRIC / CR-LIQUID-STRENGTH classes stay unmeasurable for
it. Re-extract (m3) or regenerate gold (m1) to get real v2 values.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from contracts.validate import SPEAKER_FROM_ROLE, validate_doc

__all__ = ["SPEAKER_FROM_ROLE", "migrate_gold", "migrate_record"]

_NULL_MED_FIELDS = {
    "route": None,
    "strength_value": None,
    "strength_unit": None,
    "formulation": None,
    "as_needed": None,
    "food_timing": None,
}


def _check(kind: str, doc: Any) -> None:
    errs = validate_doc(f"{kind}.v1", doc)
    if errs:
        raise ValueError(f"input is not a valid {kind}.v1 document: {errs[:5]}")


def migrate_record(rec: dict[str, Any]) -> dict[str, Any]:
    """record.v1 -> record.v2 (new copy; the input is not changed). Raises ValueError on bad input."""
    _check("record", rec)
    out = copy.deepcopy(rec)
    out["schema_version"] = "record.v2"
    out["patient_age_band"] = None
    out["weight_kg"] = None
    out["medications"] = [
        {**m, **_NULL_MED_FIELDS, "status": "unknown", "speaker": "unknown", "field_evidence": {}}
        for m in out["medications"]
    ]
    out["advice"] = [{**a, "speaker": "unknown"} for a in out["advice"]]
    errs = validate_doc("record.v2", out)
    if errs:  # fail closed: never hand out an invalid v2 document
        raise ValueError(f"migration produced an invalid record.v2: {errs[:5]}")
    return out


def migrate_gold(gold: dict[str, Any]) -> dict[str, Any]:
    """gold.v1 -> gold.v2 (new copy). speaker comes from the role of the span's turn."""
    _check("gold", gold)
    out = copy.deepcopy(gold)
    out["schema_version"] = "gold.v2"
    turns = out["turns"]

    def speaker(item: dict[str, Any]) -> str:
        return SPEAKER_FROM_ROLE[turns[item["gold_span"]["turn_index"]]["speaker_role"]]

    gr = out["gold_record"]
    gr["patient_age_band"] = None
    gr["weight_kg"] = None
    gr["medications"] = [
        {
            **m,
            **_NULL_MED_FIELDS,
            "status": "unknown",
            "speaker": speaker(m),
            "gold_field_spans": {},
        }
        for m in gr["medications"]
    ]
    gr["advice"] = [{**a, "speaker": speaker(a)} for a in gr["advice"]]
    errs = validate_doc("gold.v2", out)
    if errs:
        raise ValueError(f"migration produced an invalid gold.v2: {errs[:5]}")
    return out


def _read(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return [json.loads(text)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m contracts.migrate_v1_to_v2", description=__doc__.split("\n")[0]
    )
    ap.add_argument("kind", choices=["record", "gold"])
    ap.add_argument("path", help="a v1 .json file or a .jsonl file (one document per line)")
    ap.add_argument("-o", "--out", help="output file (.json or .jsonl); default: stdout")
    args = ap.parse_args(argv)
    src = Path(args.path)
    if not src.is_file():
        print(f"{src}: no such file", file=sys.stderr)
        return 2
    fn = migrate_record if args.kind == "record" else migrate_gold
    try:
        docs = [fn(d) for d in _read(src)]
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"not converted: {exc}", file=sys.stderr)
        return 1
    if args.out and Path(args.out).suffix == ".json" and len(docs) == 1:
        body = json.dumps(docs[0], ensure_ascii=False, indent=2) + "\n"
    else:
        body = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs)
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"converted {len(docs)} {args.kind} document(s) -> {args.out}")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
