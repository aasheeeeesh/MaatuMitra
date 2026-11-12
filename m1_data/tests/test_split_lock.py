"""The frozen TEST split (data/splits/test.lock).

1. Every line of the lock still matches its file (this is what CI / `make split-lock` checks).
2. The lock lists EVERY test file: gold label, gold transcript, test twins, test.txt.
3. Proof the check works: on a temporary COPY, editing one test file makes it fail.
"""

from __future__ import annotations

import shutil

from m1_data.split import LOCK_PATH, read_lock, verify_lock

from .conftest import DATA, ROOT


def test_lock_matches_files():
    problems = verify_lock(LOCK_PATH, ROOT)
    assert problems == [], problems[:5]


def test_lock_lists_every_test_file(split_ids):
    locked = set(read_lock(LOCK_PATH))
    want = {"data/splits/test.txt", "data/twins/twins_test.jsonl"}
    for cid in split_ids["test"]:
        want |= {f"data/gold/{cid}.json", f"data/transcripts/gold/{cid}__gold.json"}
    assert want <= locked
    for cid in split_ids["dev"]:
        assert f"data/gold/{cid}.json" not in locked


def test_lock_fails_when_a_test_file_is_edited(tmp_path, split_ids):
    copy = tmp_path / "repo"
    (copy / "data").mkdir(parents=True)
    for sub in ("gold", "gold_v2", "transcripts", "twins", "splits"):
        shutil.copytree(DATA / sub, copy / "data" / sub)
    lock = copy / "data" / "splits" / "test.lock"
    assert verify_lock(lock, copy) == []
    victim = copy / "data" / "gold" / f"{split_ids['test'][0]}.json"
    old = victim.read_bytes()
    # flip one gold label (a real label edit, byte-exact: no newline translation)
    new = (
        old.replace(b'"has_negation": true', b'"has_negation": false', 1)
        if b'"has_negation": true' in old
        else old.replace(b'"has_negation": false', b'"has_negation": true', 1)
    )
    assert new != old
    victim.write_bytes(new)
    other = copy / "data" / "transcripts" / "gold" / f"{split_ids['test'][1]}__gold.json"
    other.write_bytes(other.read_bytes() + b" ")
    problems = verify_lock(lock, copy)
    assert len(problems) == 2, problems
    assert all("CHANGED" in p for p in problems)
    victim.unlink()
    assert any("missing" in p for p in verify_lock(lock, copy))
