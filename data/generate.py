"""Thin CLI entry for the m1_data generator (AGENT 2 step 3).

    uv run python data/generate.py              # = python -m m1_data generate
    uv run python data/generate.py --refreeze   # only with a decision entry (test split changes)

Fixed seed and version live in m1_data/config.py (SEED, VERSION).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m1_data.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["generate", *sys.argv[1:]]))
