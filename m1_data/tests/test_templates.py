"""data/templates/*.yaml: count, families, typed slots, grounding in fetched sources."""

from __future__ import annotations

import re

from m1_data.templates import SLOT_TYPES, TEMPLATES_DIR, load_templates

CATEGORIES = set("abcdefghi")


def test_at_least_40_templates_in_9_categories():
    ts = load_templates()
    assert len(ts) >= 40
    assert {t.category for t in ts} == CATEGORIES
    assert len({t.id for t in ts}) == len(ts)


def test_each_family_belongs_to_one_category_and_each_category_has_two_families():
    ts = load_templates()
    fam_cat = {}
    for t in ts:
        assert fam_cat.setdefault(t.family, t.category) == t.category
        assert t.family.startswith(t.category + "_")
    for c in CATEGORIES:
        assert len({f for f, cat in fam_cat.items() if cat == c}) >= 2, c


def test_slots_are_typed_and_used():
    for t in load_templates():
        assert t.slots, t.id
        for sid, spec in t.slots.items():
            assert spec["type"] in SLOT_TYPES, (t.id, sid)
        text = " ".join(turn["text"] for turn in t.turns)
        for sid in t.slots:
            used = re.search(r"\{" + sid + r"[}.]", text) or any(
                sid in str(f) for s in t.slots.values() for f in s.get("forms", [])
            )
            assert used, f"{t.id}: slot {sid} declared but never used"
        assert 2 <= len(t.turns) <= 6, t.id
        assert t.items, t.id


def test_grounding_ids_exist_in_sources_md():
    src = (TEMPLATES_DIR / "SOURCES.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"^\| (KN-\d+) \|", src, flags=re.M))
    assert len(ids) >= 5
    assert src.count("https://") >= 5
    for t in load_templates():
        assert t.grounding, t.id
        for g in t.grounding:
            assert g in ids, (t.id, g)
