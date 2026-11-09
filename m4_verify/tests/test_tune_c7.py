"""C7 threshold tuning helper (DEV only). Checked on the hand-made fixture ASR pair."""

from __future__ import annotations

import json

import pytest

from m4_verify.tests.helpers import FIX
from m4_verify.tune_c7 import main, tune

T = FIX / "transcript" / "valid"


def _load(name):
    return json.loads((T / name).read_text(encoding="utf-8"))


def test_tune_finds_the_wrong_digit_token():
    res = tune([(_load("fx-pharm-003__asr_digit_error.json"), _load("fx-pharm-003__gold.json"))], 0.2)
    assert res["n_wrong"] == 1  # "50" is not in the gold text
    assert res["chosen"] is not None
    assert res["chosen"]["recall"] == 1.0 and res["chosen"]["flag_rate"] <= 0.2


def test_tune_refuses_test_split_paths(tmp_path):
    p = tmp_path / "pairs_test.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        main(str(p), 0.2)
