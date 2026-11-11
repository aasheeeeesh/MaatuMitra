"""Verifier configuration (YAML). Everything tunable lives here, nothing is hidden in code.

c7_conf_threshold: the C7 ASR-confidence cutoff. It MUST be tuned on the DEV split only
(m4_verify/tune_c7.py). Until a DEV ASR run exists the value is a documented PLACEHOLDER
(c7_threshold_status says so) and every report must say "C7 threshold UNTUNED".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_LEXICON = ROOT / "fixtures" / "lexicon" / "drugs_fixture.csv"
DATA_LEXICON = ROOT / "data" / "lexicon" / "drugs.csv"
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "default.yaml"
CHECK_IDS = tuple(f"C{i}" for i in range(1, 9))
VERIFIER_VERSION = "m4_verify-1.0.0"

# The lexicon has no "allowed units" column (contract gap, see handoff/open_questions.md).
# Allowed units per drug, first match wins (clinical review M4-M3, fix pass 2026-11-11):
#   1. the m4 config table `allowed_units_by_drug` (YAML, each row documented there);
#   2. units derived from the dosage form named in the lexicon's verified_by note
#      (lexicon.units_from_note: tablet, capsule, syrup, sachet, powder for injection);
#   3. this default: solid oral forms only. ml, sachet and teaspoon are NOT allowed by default
#      (a liquid needs a known strength), nor IU or drops.
DEFAULT_ALLOWED_UNITS = ("mg", "g", "mcg", "tablet", "capsule")


def default_lexicon_path() -> Path:
    """data/lexicon/drugs.csv once m1 delivers it, else the fixture lexicon. MODE=mock forces fixtures."""
    if os.environ.get("MODE") == "mock":
        return FIXTURE_LEXICON
    return DATA_LEXICON if DATA_LEXICON.exists() else FIXTURE_LEXICON


@dataclass(frozen=True)
class Config:
    lexicon_path: str = ""
    disabled: frozenset[str] = frozenset()
    c7_conf_threshold: float = 0.6
    c7_threshold_status: str = "UNTUNED placeholder (no DEV ASR run yet)"
    allowed_units: tuple[str, ...] = DEFAULT_ALLOWED_UNITS
    allowed_units_by_drug: dict[str, tuple[str, ...]] = field(default_factory=dict)
    blank_range_fails_closed: bool = True

    def lexicon(self):
        from m4_verify.lexicon import load_lexicon

        return load_lexicon(self.lexicon_path or default_lexicon_path())

    def _units(self, drug: str, lex=None) -> tuple[tuple[str, ...], str, bool]:
        from m4_verify.lexicon import units_from_note

        if drug in self.allowed_units_by_drug:
            return self.allowed_units_by_drug[drug], "m4 config table allowed_units_by_drug", False
        d = lex.drugs.get(drug) if lex is not None else None
        got = units_from_note(d.verified_by) if d is not None else None
        if got is not None:
            return got[0], "lexicon verified_by note (dosage form)", got[1]
        return self.allowed_units, "m4 default allowed_units (UNVERIFIED)", False

    def units_for(self, drug: str, lex=None) -> tuple[str, ...]:
        """Allowed dose units for a drug (see DEFAULT_ALLOWED_UNITS for the order of sources)."""
        return self._units(drug, lex)[0]

    def units_source(self, drug: str, lex=None) -> str:
        return self._units(drug, lex)[1]

    def injection_only(self, drug: str, lex=None) -> bool:
        """True if the lexicon note names only an injection form (route check, CR-ROUTE)."""
        return self._units(drug, lex)[2]


def _check_ids(ids) -> frozenset[str]:
    ids = frozenset(i.strip().upper() for i in ids)
    bad = ids - set(CHECK_IDS)
    if bad:
        raise ValueError(f"unknown check id(s) {sorted(bad)}; valid: {', '.join(CHECK_IDS)}")
    return ids


def default_config(disabled=(), **overrides) -> Config:
    cfg = load_config(DEFAULT_CONFIG) if DEFAULT_CONFIG.exists() else Config()
    if disabled:
        cfg = replace(cfg, disabled=cfg.disabled | _check_ids(disabled))
    return replace(cfg, **overrides) if overrides else cfg


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    kw = {}
    if raw.get("lexicon_path"):
        p = Path(raw["lexicon_path"])
        kw["lexicon_path"] = str(p if p.is_absolute() else ROOT / p)
    if "disabled" in raw:
        kw["disabled"] = _check_ids(raw["disabled"] or [])
    if "c7_conf_threshold" in raw:
        kw["c7_conf_threshold"] = float(raw["c7_conf_threshold"])
    if "c7_threshold_status" in raw:
        kw["c7_threshold_status"] = str(raw["c7_threshold_status"])
    if "allowed_units" in raw:
        kw["allowed_units"] = tuple(raw["allowed_units"])
    if "allowed_units_by_drug" in raw:
        kw["allowed_units_by_drug"] = {
            k: tuple(v) for k, v in (raw["allowed_units_by_drug"] or {}).items()
        }
    if "blank_range_fails_closed" in raw:
        kw["blank_range_fails_closed"] = bool(raw["blank_range_fails_closed"])
    return Config(**kw)
