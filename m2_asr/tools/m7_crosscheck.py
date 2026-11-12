"""Cross-check: let m7's independent E1 code read results/m2_asr and compare CER with ours.

m7 currently crashes on public_real rows because it reads r["file_name"] while the FLEURS subset
file has the key "file" (see handoff/open_questions.md). This script applies an IN-MEMORY shim
(no m7 file is edited) and writes m7's tables to a scratch folder, not to results/m7_eval.

Usage: uv run python m2_asr/tools/m7_crosscheck.py <scratch_out_dir>
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from m7_eval import guard, report  # noqa: E402

_orig = guard.SplitGuard.iter_jsonl


def _patched(self, path):
    for r in _orig(self, path):
        if "file" in r and "file_name" not in r:
            r["file_name"] = r["file"]
        yield r


guard.SplitGuard.iter_jsonl = _patched
out = Path(sys.argv[1])
report.run(ROOT, "dev", out)
for r in csv.DictReader(open(out / "tables" / "e1_asr_summary.csv", encoding="utf-8")):
    if r["variant"] == "ALL_VARIANTS":
        print(r["model"], r["source"], "N =", r["n_utterances"], "CER mean =", r["cer_mean"])
