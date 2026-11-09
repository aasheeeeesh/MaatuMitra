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
# Default: oral-dose units are allowed for every drug; IU and drops are not. Per-drug
# overrides go in the YAML (allowed_units_by_drug).
DEFAULT_ALLOWED_UNITS = ("mg", "g", "mcg", "ml", "tablet", "capsule", "sachet", "teaspoon")


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

    def units_for(self, drug: str) -> tuple[str, ...]:
        return self.allowed_units_by_drug.get(drug, self.allowed_units)


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
