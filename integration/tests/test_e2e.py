"""End to end on 10 DEV conversations through the real m5 HTTP API with m4 wired in.

Skips cleanly when PostgreSQL is not reachable (needs_db). Starts the API itself on 127.0.0.1
(port INTEGRATION_API_PORT, default 8000) and stops it afterwards.
"""

from __future__ import annotations

import os

import pytest

from integration import e2e
from integration.apiserver import db_up

pytestmark = pytest.mark.needs_db


@pytest.fixture(scope="module")
def res():
    ok, why = db_up()
    if not ok:
        pytest.skip(
            f"needs_db: PostgreSQL 16 not reachable ({why}). Start: bash m5_backend/scripts/db_up.sh"
        )
    out = e2e.run_all(10, int(os.environ.get("INTEGRATION_API_PORT", e2e.PORT)))
    e2e.OUT.mkdir(parents=True, exist_ok=True)
    (e2e.OUT / "e2e_dev.md").write_text(e2e.render_md(out), encoding="utf-8")
    return out


def test_ten_dev_conversations_all_processed_and_saved(res):
    assert len(res["rows"]) == 10 and len(set(res["ids"])) == 10
    assert all(r["save_status"] == 200 and r["final_status"] == "saved" for r in res["rows"])
    assert all(r["approved_by_physician"] for r in res["rows"])


def test_dev_ids_only(res):
    test = e2e.pipeline._ids("test.txt")
    assert not set(res["ids"]) & set(test)
    assert set(res["ids"]) <= set(e2e.pipeline._ids("dev.txt"))


def test_m4_is_the_verifier_in_the_api(res):
    for r in res["rows"] + res["planted"]:
        assert r["verifier_version"].startswith("m4_verify"), r["verifier_version"]


def test_save_is_refused_while_a_flag_is_open_then_allowed_after_resolution(res):
    for r in res["rows"] + res["planted"]:
        assert r["save_without_resolution"] == (409 if r["flags"] else 200), r["id"]
        assert len(r["resolutions"]) == len(r["flags"]) or not r["flags"]


def test_planted_errors_are_flagged_and_fixed_by_edit(res):
    assert len(res["planted"]) == 2
    for r in res["planted"]:
        assert any(f.startswith("C3") for f in r["flags"]), r
        assert r["save_without_resolution"] == 409
        assert r["flags_after_edit"] == 0
        assert all(x.startswith("edited:") for x in r["resolutions"])
        assert r["final_status"] == "saved"


def test_rls_before_and_after_save_is_as_expected(res):
    for r in res["rows"] + res["planted"]:
        assert {k for k, v in r["before"].items() if v == 200} == e2e.EXPECT_BEFORE, r["id"]
        assert {k for k, v in r["after"].items() if v == 200} == e2e.EXPECT_AFTER, r["id"]


def test_record_and_transcript_round_trip_through_the_api(res):
    for r in res["rows"] + res["planted"]:
        assert r["roundtrip_json_equal"] and r["transcript_ok"], r["id"]


def test_m6_gate_loads_the_draft_with_its_transcript(res):
    assert len(res["m6"]) == 3
    for m in res["m6"]:
        assert m["login"] and m["loaded"] and m["case_errors"] == [], m


def test_a_saved_record_cannot_be_verified_again(res):
    # m5's /verify only takes draft/flagged/approved rows; a saved record is final
    for r in res["rows"]:
        assert r["verify_after_save"] in (404, 409), (r["id"], r["verify_after_save"])
