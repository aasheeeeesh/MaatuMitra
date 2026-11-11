"""D-90 guard: no m3 phrase, regex or code file may contain a token that occurs ONLY in TEST-family
templates. The token set is computed from template TEXT (data/templates/*.yaml, families mapped to
test in data/splits/split_plan.json). No test transcript or test gold is read."""

from __future__ import annotations

import json
from pathlib import Path

import regex
import yaml

from m3_extract.tests._helpers import ROOT

TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
KANNADA = regex.compile(r"[\u0C80-\u0CFF]")
M3 = ROOT / "m3_extract"


def _texts(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "text" and isinstance(v, str):
                yield v
            else:
                yield from _texts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _texts(v)


def _toks(s: str) -> set[str]:
    return {
        t for t in TOKEN.findall(s.replace("\u200c", "").replace("\u200d", "")) if KANNADA.search(t)
    }


def template_token_sets() -> tuple[set[str], set[str]]:
    plan = json.loads((ROOT / "data" / "splits" / "split_plan.json").read_text(encoding="utf-8"))
    test_fams = set(plan["families"]["test"])
    dev_side: set[str] = set()
    test_side: set[str] = set()
    for p in sorted((ROOT / "data" / "templates").glob("*.yaml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        if p.name == "_forms.yaml":  # slot fills: shared by dev and test, count as dev-visible
            dev_side |= _toks(p.read_text(encoding="utf-8"))
            continue
        for fam in doc.get("families", []):
            toks = set()
            for t in _texts(fam):
                toks |= _toks(t)
            (test_side if fam["id"] in test_fams else dev_side).update(toks)
    # Other legitimate sources a builder may read: DEV gold transcripts (ids from dev.txt only; the
    # id guard in splits.py refuses test ids), and fixtures (NOT the negation table or the annotation guide: D-90 wants the words gone).
    from m3_extract.splits import GOLD_TRANSCRIPTS, dev_ids

    for cid in dev_ids():
        doc = json.loads((GOLD_TRANSCRIPTS / f"{cid}__gold.json").read_text(encoding="utf-8"))
        dev_side |= _toks(doc["text"])
    for p in (ROOT / "fixtures").rglob("*.json"):
        dev_side |= _toks(p.read_text(encoding="utf-8"))
    return dev_side, test_side - dev_side


def m3_files():
    out = [p for p in M3.rglob("*") if p.suffix in (".py", ".yaml") and "merged" not in p.parts]
    return [p for p in out if p.name != Path(__file__).name]


def offenders() -> list[tuple[str, str]]:
    dev_side, test_only = template_token_sets()
    dev_blob = "\n".join(sorted(dev_side))
    bad = []
    for p in m3_files():
        for frag in _toks(p.read_text(encoding="utf-8")):
            if frag in test_only:
                bad.append((p.name, frag))
            elif len(frag) >= 2 and frag not in dev_side and frag not in dev_blob:
                # a fragment (regex branch, stem) found inside a test-only token and nowhere in dev text
                if any(frag in t for t in test_only):
                    bad.append((p.name, frag))
    return bad


def test_token_sets_are_nonempty_and_disjoint():
    dev_side, test_only = template_token_sets()
    assert len(dev_side) > 100 and len(test_only) > 10
    assert not (dev_side & test_only)


def test_no_m3_file_contains_a_test_only_word():
    assert offenders() == []
