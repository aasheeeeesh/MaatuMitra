"""Seen-frame vs unseen-frame marker (D-90): which TEST template turns reuse a sentence frame
that also occurs in a DEV template. Computed from data/templates/*.yaml (template text only,
never from test conversations, gold or audio). A frame = the turn text with gold-span markers
unwrapped and every {slot} replaced by one placeholder, then comparison-normalised.
Output rows carry ids and booleans only, no text.
"""

from __future__ import annotations

import regex
import yaml

from m7_eval import textnorm as tn

SPAN = regex.compile(r"\[\[[^|\]]+\|(.*?)\]\]")
SLOT = regex.compile(r"\{[^}]*\}")
CLAUSE = regex.compile(r"[?!,;:।\n]|\.(?!\p{L})")
CONV = regex.compile(r"^m1-([a-z]\d+)-\d+$")


def frame(text: str) -> str:
    s = SPAN.sub(lambda m: m.group(1), text)
    s = SLOT.sub(" SLOT ", s)
    return tn.compare_norm(s)


def clause_frames(text: str) -> list[str]:
    f = frame(text)
    return [c.strip(" .") for c in CLAUSE.split(f) if c.strip(" .")]


def frame_status(text: str, dev_turns: set[str]) -> str:
    """'slot_only' (the turn is only a slot, e.g. a cross-turn yes/no answer: no frame to
    share), 'seen' (the same frame occurs in a DEV template) or 'unseen'."""
    f = frame(text)
    toks = tn.TOKEN.findall(f)
    if toks and all(t == "slot" for t in toks):
        return "slot_only"
    return "seen" if f in dev_turns else "unseen"


def template_of(conv_id: str) -> str | None:
    m = CONV.match(conv_id)
    return m.group(1) if m else None


def load_families(guard, split_plan: dict) -> dict[str, tuple[str, list[dict]]]:
    """{family_id: (split, [template dict])} from data/templates/*.yaml (read via the guard)."""
    fam_split = {f: s for s, fs in split_plan["families"].items() for f in fs}
    out: dict[str, tuple[str, list[dict]]] = {}
    for p in guard.listdir("data/templates", "*.yaml"):
        if p.name.startswith("_"):
            continue
        doc = yaml.safe_load(guard.read_text(p)) or {}
        for fam in doc.get("families", []):
            out[fam["id"]] = (fam_split.get(fam["id"], "unknown"), fam.get("templates", []))
    return out


def overlap_rows(families: dict[str, tuple[str, list[dict]]]) -> list[dict]:
    dev_turns, dev_clauses = set(), set()
    for split, temps in families.values():
        if split == "dev":
            for t in temps:
                for turn in t["turns"]:
                    dev_turns.add(frame(turn["text"]))
                    dev_clauses.update(clause_frames(turn["text"]))
    rows = []
    for fam in sorted(families):
        split, temps = families[fam]
        for t in temps:
            for i, turn in enumerate(t["turns"]):
                cl = clause_frames(turn["text"])
                rows.append(
                    {
                        "family_id": fam,
                        "template_id": t["id"],
                        "split": split,
                        "turn_index": i,
                        "turn_frame_seen_in_dev": frame(turn["text"]) in dev_turns,
                        "frame_status": frame_status(turn["text"], dev_turns),
                        "n_clauses": len(cl),
                        "clauses_seen_in_dev": sum(c in dev_clauses for c in cl),
                    }
                )
    return rows
