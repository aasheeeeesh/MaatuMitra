"""Fixed constants of the m1_data generator. Change VERSION whenever output changes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "m1-data-1.1.0"
SEED = 20261109
# Fixed timestamp written into every generated file (never "now": keeps output deterministic).
CREATED_AT = "2026-11-09T00:00:00Z"
NEGATION_TABLE = ROOT / ".claude" / "skills" / "kannada-nlp" / "negation_table.yaml"
CONSENT_NOTE = "template-generated synthetic text; no person involved"
