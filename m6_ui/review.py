"""Pure review logic (no Streamlit): record -> rows, verdict flags -> rows, Approve rule.

Rules (PROJECT_BRIEF AGENT 7):
- flagged rows FIRST (stable: record order inside each group);
- a flag that does not map to a row is shown on a "whole record" row, never dropped;
- missing verdict / empty checks is fail-closed (a synthetic flag on "/");
- Approve is enabled only when EVERY current flag was individually confirmed or edited.
  A flag is identified by (check id, field path, reason), so a NEW flag produced by a
  verifier re-run is not pre-resolved.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

KINDS = (
    "symptom",
    "drug",
    "dose",
    "frequency",
    "duration",
    "med_negated",
    "advice",
    "follow_up",
    "record",
)

# Editable attributes per row kind: (attribute path suffix relative to the item, input type, i18n label key)
EDIT_SPEC: dict[str, list[tuple[str, str, str]]] = {
    "symptom": [("name", "text", "attr.name"), ("present", "bool", "attr.present")],
    "drug": [("drug", "text", "attr.drug")],
    "dose": [("dose_value", "number", "attr.dose_value"), ("dose_unit", "unit", "attr.dose_unit")],
    "frequency": [("frequency_per_day", "number", "attr.frequency_per_day")],
    "duration": [("duration_days", "number", "attr.duration_days")],
    "med_negated": [("negated", "bool", "attr.negated_med")],
    "advice": [("text", "text", "attr.text"), ("negated", "bool", "attr.negated_advice")],
    "follow_up": [("text", "text", "attr.text")],
    "record": [],
}

UNITS = ["mg", "g", "mcg", "ml", "tablet", "capsule", "sachet", "drop", "teaspoon", "IU", None]

NO_VERDICT_CHECK = "none"


@dataclass(frozen=True)
class Flag:
    check_id: str
    name: str
    reason: str
    field_path: str

    @property
    def flag_id(self) -> str:
        return f"{self.check_id}|{self.field_path}|{self.reason}"


@dataclass
class Row:
    path: str  # canonical JSON pointer of the row
    kind: str
    item_path: str  # pointer of the record item ("/medications/0"), "" for the record row
    covers: tuple[str, ...]  # pointers whose flags land on this row
    evidence: dict | None
    flags: list[Flag] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.path.strip("/").replace("/", "-") or "record"


# --------------------------------------------------------------------------- pointers


def _tokens(path: str) -> list[str]:
    return [p for p in path.split("/")[1:] if p != ""]


def get_pointer(doc: Any, path: str) -> Any:
    cur = doc
    for tok in _tokens(path):
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def set_pointer(doc: dict, path: str, value: Any) -> dict:
    new = copy.deepcopy(doc)
    toks = _tokens(path)
    cur = new
    for tok in toks[:-1]:
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    last = toks[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value
    return new


# --------------------------------------------------------------------------- flags


def flags_from_verdict(verdict: dict | None) -> list[Flag]:
    """Every flagging check. Missing verdict or empty checks -> one fail-closed flag on '/'."""
    if verdict is None:
        return [Flag(NO_VERDICT_CHECK, "no-verdict", "no_verdict", "/")]
    checks = verdict.get("checks") or []
    if not checks:
        return [Flag(NO_VERDICT_CHECK, "no-checks", "none", "/")]
    return [
        Flag(c["check_id"], c.get("name", ""), c.get("reason", ""), c.get("field_path", "/"))
        for c in checks
        if c.get("status") == "flag"
    ]


# --------------------------------------------------------------------------- rows


def _item_rows(record: dict) -> list[Row]:
    rows: list[Row] = []
    for i, s in enumerate(record.get("symptoms", [])):
        base = f"/symptoms/{i}"
        rows.append(Row(base, "symptom", base, (base,), s.get("evidence")))
    for i, m in enumerate(record.get("medications", [])):
        base = f"/medications/{i}"
        ev = m.get("evidence")
        rows += [
            Row(f"{base}/drug", "drug", base, (base, f"{base}/drug", f"{base}/evidence"), ev),
            Row(
                f"{base}/dose_value", "dose", base, (f"{base}/dose_value", f"{base}/dose_unit"), ev
            ),
            Row(f"{base}/frequency_per_day", "frequency", base, (f"{base}/frequency_per_day",), ev),
            Row(f"{base}/duration_days", "duration", base, (f"{base}/duration_days",), ev),
            Row(f"{base}/negated", "med_negated", base, (f"{base}/negated",), ev),
        ]
    for i, a in enumerate(record.get("advice", [])):
        base = f"/advice/{i}"
        rows.append(Row(base, "advice", base, (base,), a.get("evidence")))
    if record.get("follow_up"):
        rows.append(
            Row(
                "/follow_up",
                "follow_up",
                "/follow_up",
                ("/follow_up",),
                record["follow_up"].get("evidence"),
            )
        )
    return rows


def build_rows(record: dict, verdict: dict | None) -> list[Row]:
    rows = _item_rows(record)
    record_row = Row("/", "record", "", ("/",), None)
    for flag in flags_from_verdict(verdict):
        p = flag.field_path
        target = next((r for r in rows if p in r.covers), None)
        if (
            target is None
        ):  # a sub-path of an item, e.g. /symptoms/1/present or /medications/0/evidence
            target = next(
                (r for r in rows if r.item_path and p.startswith(r.item_path + "/")), None
            )
        (target or record_row).flags.append(flag)
    if record_row.flags:
        rows.insert(0, record_row)
    flagged = [r for r in rows if r.flags]
    return flagged + [r for r in rows if not r.flags]


# --------------------------------------------------------------------------- resolution


def mark_row(resolved: dict, row: Row, how: str) -> None:
    """Record the reviewer's answer for every CURRENT flag on this row ('confirmed' or 'edited')."""
    if how not in ("confirmed", "edited"):
        raise ValueError(how)
    for f in row.flags:
        resolved[f.flag_id] = how


def unmark_row(resolved: dict, row: Row) -> None:
    for f in row.flags:
        resolved.pop(f.flag_id, None)


def row_state(resolved: dict, row: Row) -> str | None:
    """'confirmed' / 'edited' if every flag on the row is answered, else None."""
    if not row.flags:
        return None
    states = [resolved.get(f.flag_id) for f in row.flags]
    if any(s is None for s in states):
        return None
    return "edited" if "edited" in states else "confirmed"


def unresolved(verdict: dict | None, resolved: dict) -> list[Flag]:
    flags = flags_from_verdict(verdict)
    # fail-closed pseudo flags (no verdict / no checks) can be acknowledged but never "auto" pass
    return [f for f in flags if f.flag_id not in resolved]


def approve_enabled(verdict: dict | None, resolved: dict) -> bool:
    if verdict is None or not (verdict.get("checks") or []):
        # fail-closed: the reviewer must explicitly acknowledge the missing verifier result
        return not unresolved(verdict, resolved) and bool(resolved)
    return not unresolved(verdict, resolved)
