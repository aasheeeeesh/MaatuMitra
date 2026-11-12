"""Load and validate data/templates/*.yaml (see data/templates/README.md for the format)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import regex
import yaml

from m1_data.config import ROOT
from m1_data.goldv2 import check_item_keys
from m1_data.render import SYMPTOMS

TEMPLATES_DIR = ROOT / "data" / "templates"
SLOT_TYPES = {"drug", "symptom", "count", "word", "neg", "xturn"}
ITEM_KINDS = {"symptom", "medication", "advice", "follow_up"}
ENCOUNTERS = {"asha_household_visit", "nurse_consult", "physician_consult", "pharmacist_dispensing"}
ROLES = {"asha", "nurse", "physician", "pharmacist", "patient", "caregiver"}
XTURN_FORMS = [
    {"neg": "ಇಲ್ಲ.", "pos": "ಹೌದು.", "patterns": ["NEG-X01", "NEG-W01"]},
    {"neg": "ಇಲ್ಲಾ.", "pos": "ಹೌದು.", "patterns": ["NEG-X01", "NEG-W02"]},
]


@dataclass
class Template:
    id: str
    category: str
    family: str
    encounter: str
    grounding: list[str]
    n: int
    slots: dict
    turns: list[dict]
    items: list[dict]
    source_file: str


def _resolve_forms(spec: dict, form_sets: dict, where: str) -> list[dict]:
    forms = spec["forms"]
    if isinstance(forms, str):
        forms = form_sets[forms]
    subj = spec.get("subject")
    out = []
    for f in forms:
        f = dict(f)
        for k in ("neg", "pos"):
            f[k] = str(f[k])
            if "$S" in f[k]:
                if not subj:
                    raise ValueError(f"{where}: form uses $S but slot has no subject")
                f[k] = f[k].replace("$S", subj)
        if not f.get("patterns"):
            raise ValueError(f"{where}: form without patterns")
        out.append(f)
    return out


def _check(t: Template) -> None:
    w = f"{t.source_file}:{t.id}"
    if t.encounter not in ENCOUNTERS:
        raise ValueError(f"{w}: bad encounter {t.encounter}")
    if not 2 <= len(t.turns) <= 6:
        raise ValueError(f"{w}: needs 2-6 turns")
    for turn in t.turns:
        if turn["role"] not in ROLES:
            raise ValueError(f"{w}: bad role {turn['role']}")
    for sid, s in t.slots.items():
        if s["type"] not in SLOT_TYPES:
            raise ValueError(f"{w}: slot {sid} has unknown type {s['type']}")
        if s["type"] == "symptom":
            bad = set(s["pool"]) - set(SYMPTOMS)
            if bad:
                raise ValueError(f"{w}: unknown symptoms {bad}")
    markers = set(regex.findall(r"\[\[([a-z]+\d*)\|", " ".join(x["text"] for x in t.turns)))
    for it in t.items:
        if it["kind"] not in ITEM_KINDS:
            raise ValueError(f"{w}: bad item kind {it['kind']}")
        if it["kind"] == "medication":
            check_item_keys(it, f"{w}:{it['span']}")
            for key in (
                "status_span",
                "formulation_span",
                "route_span",
                "as_needed_span",
                "food_span",
                "strength_span",
            ):
                if it.get(key) and it[key] not in markers:
                    raise ValueError(f"{w}: {key} {it[key]!r} is not a marker in the turns")
        neg = it.get("neg")
        if neg:
            spec = t.slots[neg]
            if (
                spec.get("p_neg", 1.0) < 1.0
                and it["kind"] in ("advice", "follow_up")
                and "text_pos" not in it
            ):
                raise ValueError(
                    f"{w}: item {it['span']} needs text_pos (slot {neg} may be positive)"
                )


def load_templates(directory: Path = TEMPLATES_DIR) -> list[Template]:
    form_sets = yaml.safe_load((directory / "_forms.yaml").read_text(encoding="utf-8"))["form_sets"]
    out: list[Template] = []
    for p in sorted(directory.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        cat = d["category"]
        for fam in d["families"]:
            for raw in fam["templates"]:
                slots = {}
                for sid, s in (raw.get("slots") or {}).items():
                    s = dict(s)
                    if s["type"] == "neg":
                        s["forms"] = _resolve_forms(s, form_sets, f"{p.name}:{raw['id']}:{sid}")
                    elif s["type"] == "xturn":
                        s["forms"] = XTURN_FORMS
                    slots[sid] = s
                t = Template(
                    id=raw["id"],
                    category=cat,
                    family=fam["id"],
                    encounter=raw.get("encounter", fam.get("encounter", d.get("encounter"))),
                    grounding=raw.get("grounding", fam.get("grounding", d.get("grounding", []))),
                    n=int(raw.get("n", fam.get("n", d.get("n", 8)))),
                    slots=slots,
                    turns=raw["turns"],
                    items=raw["items"],
                    source_file=p.name,
                )
                _check(t)
                out.append(t)
    ids = [t.id for t in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate template ids")
    return out
