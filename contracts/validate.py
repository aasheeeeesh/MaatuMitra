"""Validate MaatuMitra contract documents: JSON Schema (draft 2020-12) + semantic rules.

This is a CONTRACT TOOL, not module code: every module may import it.

Usage (from the repo root):
    uv run python -m contracts.validate <schema_name> <file.json|file.jsonl|dir> [...]
    uv run python -m contracts.validate --check-fixtures fixtures
    uv run python -m contracts.validate --list

<schema_name> may be "transcript" or "transcript.v1".
Exit code: 0 = everything valid, 1 = at least one invalid document, 2 = usage error.

Semantic rules (beyond JSON Schema) -- see contracts/CHANGELOG.md and
docs/DECISIONS_EXPLAINED.md:
  * every string is Unicode NFC and contains no BOM (U+FEFF) or zero-width space (U+200B)
  * timestamps parse as real ISO-8601 date-times
  * transcript: words[i].w == text[char_start:char_end]; char_end > char_start; words in order
  * record: evidence char_end > char_start and char_end - char_start == len(span_text);
    audio_end >= audio_start. (Matching a span against its transcript needs the transcript;
    that is done by the producing/consuming module and by tests/test_contracts.py.)
  * verdict: auto_acceptable must be false if any check has status "flag" or if checks is empty;
    a reason starting "check_error" must have status "flag" (fail-closed)
  * gold: every gold_span equals conversation_text[char_start:char_end] and lies inside its turn;
    tags.has_negation must be true if any gold item is negated / absent
  * access_case: authentication/GUC attacks must expect "deny"
  * card: kn_text must contain Kannada script (U+0C80..U+0CFF)
  * review_report: finding ids unique
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections.abc import Callable, Iterator
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
FORBIDDEN_CHARS = {"﻿": "BOM U+FEFF", "​": "zero-width space U+200B"}
TIMESTAMP_FIELDS = {"created_at", "retrieved_at", "source_retrieved_at"}
AUTH_ATTACKS_MUST_DENY = {"tampered_jwt", "expired_jwt", "alg_none", "wrong_aud", "guc_tamper"}


# ---------------------------------------------------------------- schema access


def list_schemas() -> list[str]:
    return sorted(p.name.removesuffix(".schema.json") for p in SCHEMA_DIR.glob("*.schema.json"))


def _canonical(name: str) -> str:
    name = name.removesuffix(".schema.json")
    if name in list_schemas():
        return name
    if f"{name}.v1" in list_schemas():
        return f"{name}.v1"
    raise KeyError(f"unknown schema {name!r}; known: {', '.join(list_schemas())}")


@cache
def load_schema(name: str) -> dict[str, Any]:
    name = _canonical(name)
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


# ---------------------------------------------------------------- helpers


def conversation_text(turns: list[dict[str, Any]]) -> str:
    """Canonical conversation text for gold.v1: turn texts joined by one newline."""
    return "\n".join(t["text"] for t in turns)


def _walk_strings(obj: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(obj, str):
        yield path or "/", obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}/{i}")


def _walk_keys(obj: Any, path: str = "") -> Iterator[tuple[str, str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}/{k}", k, v
            yield from _walk_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, f"{path}/{i}")


def _common(doc: Any) -> list[str]:
    errs: list[str] = []
    for path, s in _walk_strings(doc):
        if unicodedata.normalize("NFC", s) != s:
            errs.append(f"{path}: string is not Unicode NFC")
        for ch, label in FORBIDDEN_CHARS.items():
            if ch in s:
                errs.append(f"{path}: contains {label}")
    for path, key, val in _walk_keys(doc):
        if key in TIMESTAMP_FIELDS and isinstance(val, str):
            try:
                datetime.fromisoformat(val)
            except ValueError:
                errs.append(f"{path}: not a real ISO-8601 date-time: {val!r}")
    return errs


def _span_basic(ev: dict[str, Any], path: str, *, audio: bool) -> list[str]:
    errs = []
    cs, ce = ev["char_start"], ev["char_end"]
    if ce <= cs:
        errs.append(f"{path}: char_end ({ce}) must be > char_start ({cs})")
    elif ce - cs != len(ev["span_text"]):
        errs.append(
            f"{path}: char_end - char_start ({ce - cs}) != len(span_text) ({len(ev['span_text'])})"
        )
    if audio:
        a0, a1 = ev.get("audio_start"), ev.get("audio_end")
        if (a0 is None) != (a1 is None):
            errs.append(f"{path}: audio_start and audio_end must both be null or both set")
        elif a0 is not None and a1 < a0:
            errs.append(f"{path}: audio_end < audio_start")
    return errs


def _record_items(rec: dict[str, Any], span_key: str) -> Iterator[tuple[str, dict[str, Any]]]:
    for group in ("symptoms", "medications", "advice"):
        for i, item in enumerate(rec.get(group, [])):
            yield f"/{group}/{i}", item
    if rec.get("follow_up") is not None:
        yield "/follow_up", rec["follow_up"]


# ---------------------------------------------------------------- semantic rules


def _sem_transcript(doc: dict[str, Any]) -> list[str]:
    errs = []
    text = doc["text"]
    prev_end = 0
    for i, w in enumerate(doc["words"]):
        p = f"/words/{i}"
        cs, ce = w["char_start"], w["char_end"]
        if ce <= cs:
            errs.append(f"{p}: char_end must be > char_start")
            continue
        if ce > len(text):
            errs.append(f"{p}: char_end {ce} beyond text length {len(text)}")
            continue
        if text[cs:ce] != w["w"]:
            errs.append(f"{p}: text[{cs}:{ce}] = {text[cs:ce]!r} != w {w['w']!r}")
        if cs < prev_end:
            errs.append(f"{p}: words overlap or are out of order")
        prev_end = ce
        if w["start"] is not None and w["end"] is not None and w["end"] < w["start"]:
            errs.append(f"{p}: end < start")
        dur = doc.get("audio_duration_s")
        if dur is not None and w["end"] is not None and w["end"] > dur + 0.05:
            errs.append(f"{p}: end {w['end']} beyond audio_duration_s {dur}")
    return errs


def _sem_record(doc: dict[str, Any]) -> list[str]:
    errs = []
    for path, item in _record_items(doc, "evidence"):
        errs += _span_basic(item["evidence"], f"{path}/evidence", audio=True)
    return errs


def _sem_verdict(doc: dict[str, Any]) -> list[str]:
    errs = []
    statuses = [c["status"] for c in doc["checks"]]
    if doc["auto_acceptable"] and "flag" in statuses:
        errs.append("/auto_acceptable: must be false when any check has status 'flag'")
    if doc["auto_acceptable"] and not doc["checks"]:
        errs.append("/auto_acceptable: must be false when no checks ran (fail-closed)")
    for i, c in enumerate(doc["checks"]):
        if c["reason"].startswith("check_error") and c["status"] != "flag":
            errs.append(f"/checks/{i}: a check_error must have status 'flag' (fail-closed)")
    return errs


def _sem_gold(doc: dict[str, Any]) -> list[str]:
    errs = []
    turns = doc["turns"]
    text = conversation_text(turns)
    bounds, pos = [], 0
    for t in turns:
        bounds.append((pos, pos + len(t["text"])))
        pos += len(t["text"]) + 1
    gr = doc["gold_record"]
    negated_any = False
    for path, item in _record_items(gr, "gold_span"):
        sp = item["gold_span"]
        p = f"/gold_record{path}/gold_span"
        errs += _span_basic(sp, p, audio=False)
        ti = sp["turn_index"]
        if ti >= len(turns):
            errs.append(f"{p}: turn_index {ti} out of range")
            continue
        lo, hi = bounds[ti]
        if not (lo <= sp["char_start"] and sp["char_end"] <= hi):
            errs.append(f"{p}: span [{sp['char_start']},{sp['char_end']}) not inside turn {ti}")
        elif text[sp["char_start"] : sp["char_end"]] != sp["span_text"]:
            got = text[sp["char_start"] : sp["char_end"]]
            errs.append(f"{p}: conversation text slice {got!r} != span_text")
        if item.get("negated") is True or item.get("present") is False:
            negated_any = True
    tags = doc["tags"]
    if negated_any and not tags["has_negation"]:
        errs.append("/tags/has_negation: must be true (a gold item is negated or absent)")
    if tags["cross_turn_negation"] and not tags["has_negation"]:
        errs.append("/tags/has_negation: must be true when cross_turn_negation is true")
    return errs


def _sem_manifest(doc: dict[str, Any]) -> list[str]:
    errs = []
    if doc["file"].startswith("/"):
        errs.append("/file: must be relative to the repo root")
    if ".." in Path(doc["file"]).parts:
        errs.append("/file: must not contain '..'")
    return errs


def _sem_access_case(doc: dict[str, Any]) -> list[str]:
    if doc["attack"] in AUTH_ATTACKS_MUST_DENY and doc["expected"] != "deny":
        return [f"/expected: attack {doc['attack']!r} must always expect 'deny'"]
    return []


def _sem_card(doc: dict[str, Any]) -> list[str]:
    if not any("ಀ" <= ch <= "೿" for ch in doc["kn_text"]):
        return ["/kn_text: contains no Kannada script (U+0C80..U+0CFF)"]
    return []


def _sem_review_report(doc: dict[str, Any]) -> list[str]:
    ids = [f["id"] for f in doc["findings"]]
    if len(ids) != len(set(ids)):
        return ["/findings: finding ids must be unique"]
    return []


SEMANTIC: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "transcript.v1": _sem_transcript,
    "record.v1": _sem_record,
    "verdict.v1": _sem_verdict,
    "gold.v1": _sem_gold,
    "manifest.v1": _sem_manifest,
    "access_case.v1": _sem_access_case,
    "card.v1": _sem_card,
    "review_report.v1": _sem_review_report,
}


# ---------------------------------------------------------------- public API


def validate_doc(schema_name: str, doc: Any) -> list[str]:
    """Return a list of human-readable errors (empty list = valid)."""
    name = _canonical(schema_name)
    errs = [
        f"{'/' + '/'.join(map(str, e.absolute_path))}: {e.message}"
        for e in sorted(_validator(name).iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]
    if errs:  # semantic rules assume the structure is right
        return errs + _common(doc)
    try:
        return _common(doc) + SEMANTIC[name](doc)
    except Exception as exc:  # fail closed: a crash in a rule is an error, never a pass
        return [f"semantic validator error: {type(exc).__name__}: {exc}"]


def _iter_docs(path: Path) -> Iterator[tuple[str, Any]]:
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.suffix in (".json", ".jsonl") and p.is_file():
                yield from _iter_docs(p)
        return
    if path.suffix == ".jsonl":
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                try:
                    yield f"{path}:{n}", json.loads(line)
                except json.JSONDecodeError as exc:
                    yield f"{path}:{n}", _BadJSON(str(exc))
        return
    try:
        yield str(path), json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        yield str(path), _BadJSON(str(exc))


class _BadJSON:
    def __init__(self, msg: str) -> None:
        self.msg = msg


def validate_path(schema_name: str, path: str | Path) -> dict[str, list[str]]:
    """Validate a .json file, a .jsonl file (one doc per line) or a directory of them."""
    out: dict[str, list[str]] = {}
    for where, doc in _iter_docs(Path(path)):
        if isinstance(doc, _BadJSON):
            out[where] = [f"invalid JSON: {doc.msg}"]
        else:
            out[where] = validate_doc(schema_name, doc)
    return out


def check_fixtures(fixtures_root: str | Path) -> list[str]:
    """Every fixtures/<contract>/valid/*.json must pass; every invalid/*.json must fail."""
    root = Path(fixtures_root)
    problems = []
    for name in list_schemas():
        base = name.removesuffix(".v1")
        valid = sorted((root / base / "valid").glob("*.json"))
        invalid = sorted((root / base / "invalid").glob("*.json"))
        if len(valid) < 5:
            problems.append(f"{base}: only {len(valid)} valid fixtures (need >= 5)")
        if len(invalid) < 3:
            problems.append(f"{base}: only {len(invalid)} invalid fixtures (need >= 3)")
        for p in valid:
            for where, errs in validate_path(name, p).items():
                if errs:
                    problems.append(f"VALID fixture rejected: {where}: {errs}")
        for p in invalid:
            for where, errs in validate_path(name, p).items():
                if not errs:
                    problems.append(f"INVALID fixture accepted: {where}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m contracts.validate", description=__doc__.split("\n")[0]
    )
    ap.add_argument("schema", nargs="?", help="schema name, e.g. transcript or transcript.v1")
    ap.add_argument("paths", nargs="*", help=".json / .jsonl files or directories")
    ap.add_argument(
        "--check-fixtures", metavar="DIR", help="check fixtures/<contract>/{valid,invalid}"
    )
    ap.add_argument("--list", action="store_true", help="list known schemas")
    args = ap.parse_args(argv)

    if args.list:
        print("\n".join(list_schemas()))
        return 0
    if args.check_fixtures:
        problems = check_fixtures(args.check_fixtures)
        for p in problems:
            print(p)
        n = sum(
            len(list((Path(args.check_fixtures) / s.removesuffix(".v1") / k).glob("*.json")))
            for s in list_schemas()
            for k in ("valid", "invalid")
        )
        print(f"checked {n} fixture files: {'FAIL' if problems else 'OK'}")
        return 1 if problems else 0
    if not args.schema or not args.paths:
        ap.print_usage(sys.stderr)
        return 2
    try:
        _canonical(args.schema)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    bad = total = 0
    for p in args.paths:
        if not Path(p).exists():
            print(f"{p}: no such file or directory", file=sys.stderr)
            return 2
        for where, errs in validate_path(args.schema, p).items():
            total += 1
            if errs:
                bad += 1
                print(f"INVALID {where}")
                for e in errs:
                    print(f"    {e}")
    print(f"{total - bad}/{total} valid against {_canonical(args.schema)}")
    return 1 if bad else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
