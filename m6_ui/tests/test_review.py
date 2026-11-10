"""Pure review logic: rows, flagged-first order, resolution, Approve rule."""

from __future__ import annotations

import copy

from m6_ui import review
from m6_ui.tests.helpers import fixture_triplet


def test_flagged_rows_come_first_and_keep_record_order():
    rec, ver, _ = fixture_triplet("rec-fx-nurse-005")
    rows = review.build_rows(rec, ver)
    flagged = [r for r in rows if r.flags]
    assert [r.path for r in flagged] == ["/symptoms/1"]
    assert rows[0].path == "/symptoms/1"
    first_unflagged = next(i for i, r in enumerate(rows) if not r.flags)
    assert all(not r.flags for r in rows[first_unflagged:])
    # the rest stay in record order
    rest = [r.path for r in rows[first_unflagged:]]
    assert rest == ["/symptoms/0", "/follow_up"]


def test_two_flags_on_one_field_land_on_one_row():
    rec, ver, _ = fixture_triplet("rec-fx-pharm-003-asr")
    rows = review.build_rows(rec, ver)
    assert rows[0].path == "/medications/0/dose_value"
    assert sorted(f.check_id for f in rows[0].flags) == ["C4", "C7"]
    assert sum(bool(r.flags) for r in rows) == 1


def test_unmappable_flag_goes_to_a_visible_record_row_never_dropped():
    rec, ver, _ = fixture_triplet("rec-fx-asha-001")
    ver = copy.deepcopy(ver)
    ver["checks"].append(
        {
            "check_id": "C6",
            "name": "unsupported-addition",
            "status": "flag",
            "reason": "patient link mismatch",
            "field_path": "/patient_ref",
        }
    )
    ver["auto_acceptable"] = False
    rows = review.build_rows(rec, ver)
    assert rows[0].kind == "record" and rows[0].flags[0].check_id == "C6"
    total = sum(len(r.flags) for r in rows)
    assert total == len(review.flags_from_verdict(ver))


def test_missing_or_empty_verdict_is_fail_closed():
    _rec, ver, _ = fixture_triplet("rec-fx-asha-001")
    for bad in (None, {**ver, "checks": [], "auto_acceptable": False}):
        flags = review.flags_from_verdict(bad)
        assert len(flags) == 1 and flags[0].field_path == "/"
        assert not review.approve_enabled(bad, {})


def test_clean_verdict_still_needs_a_human_click_but_is_enabled():
    _rec, ver, _ = fixture_triplet("rec-fx-asha-001")
    assert ver["auto_acceptable"] is True
    assert review.approve_enabled(ver, {}) is True


def test_approve_needs_every_flag_individually_resolved():
    rec, ver, _ = fixture_triplet("rec-m6-xss")
    rows = [r for r in review.build_rows(rec, ver) if r.flags]
    assert len(rows) == 2
    resolved: dict = {}
    assert not review.approve_enabled(ver, resolved)
    review.mark_row(resolved, rows[0], "confirmed")
    assert not review.approve_enabled(ver, resolved)
    assert len(review.unresolved(ver, resolved)) == 1
    review.mark_row(resolved, rows[1], "edited")
    assert review.approve_enabled(ver, resolved)
    review.unmark_row(resolved, rows[1])
    assert not review.approve_enabled(ver, resolved)


def test_a_new_flag_with_a_new_reason_is_not_pre_resolved():
    rec, ver, _ = fixture_triplet("rec-fx-pharm-003-asr")
    rows = review.build_rows(rec, ver)
    resolved: dict = {}
    review.mark_row(resolved, rows[0], "confirmed")
    ver2 = copy.deepcopy(ver)
    ver2["checks"].append(
        {
            "check_id": "C2",
            "name": "x",
            "status": "flag",
            "reason": "new reason",
            "field_path": "/medications/0/dose_value",
        }
    )
    assert not review.approve_enabled(ver2, resolved)


def test_pointer_get_and_set_do_not_mutate_input():
    rec, _, _ = fixture_triplet("rec-fx-pharm-003-asr")
    assert review.get_pointer(rec, "/medications/0/dose_value") == 50
    new = review.set_pointer(rec, "/medications/0/dose_value", 500)
    assert new["medications"][0]["dose_value"] == 500
    assert rec["medications"][0]["dose_value"] == 50


def test_every_row_kind_is_known():
    for rid in ["rec-fx-asha-001", "rec-fx-nurse-005", "rec-fx-phys-004", "rec-m6-xss"]:
        rec, ver, _ = fixture_triplet(rid)
        for r in review.build_rows(rec, ver):
            assert r.kind in review.KINDS
