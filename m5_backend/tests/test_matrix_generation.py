"""E5 matrix generation (no database): >= 500 cases, every case valid access_case.v1."""

from collections import Counter
from pathlib import Path

import pytest

from contracts.validate import validate_doc
from m5_backend.matrix.generate import (
    ACTIONS,
    OWNERSHIPS,
    RESOURCES,
    ROLES,
    all_cases,
    expected_for,
    load_expected,
)

EXPECTED = Path(__file__).with_name("access_matrix_expected.yaml")
ATTACKS = {
    "id_guess",
    "tampered_jwt",
    "expired_jwt",
    "alg_none",
    "wrong_aud",
    "sqli",
    "mass_assignment",
    "idor_audio",
    "guc_tamper",
}


@pytest.fixture(scope="module")
def cases():
    return all_cases(load_expected(EXPECTED))


def test_at_least_500_and_all_valid(cases):
    assert len(cases) >= 500
    bad = {c.case["case_id"]: validate_doc("access_case.v1", c.case) for c in cases}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, list(bad.items())[:3]


def test_case_ids_unique(cases):
    ids = [c.case["case_id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_full_base_cross_product(cases):
    base = [c for c in cases if c.case["case_id"].startswith("base.")]
    assert len(base) == len(ROLES) * len(RESOURCES) * len(ACTIONS) * len(OWNERSHIPS)


def test_every_attack_type_present(cases):
    seen = Counter(c.case["attack"] for c in cases if c.case["attack"])
    assert set(seen) == ATTACKS, seen
    assert all(n >= 5 for n in seen.values()), seen


def test_sqli_hits_every_text_parameter_kind(cases):
    kinds = {c.probe["param_kind"] for c in cases if c.case["attack"] == "sqli"}
    assert kinds == {"id_param", "query_param", "login_field", "text_field", "constrained_field"}


def test_guc_tamper_covers_set_user_id_and_reset_role(cases):
    variants = {c.probe["variant"] for c in cases if c.case["attack"] == "guc_tamper"}
    assert {"reset_role_then_select", "set_user_id_via_body_sql", "header_user_id"} <= variants


def test_expected_spot_checks_follow_brief():
    e = load_expected(EXPECTED)
    assert expected_for(e, "asha", "households", "select", "own") == "allow"
    assert expected_for(e, "asha", "households", "update", "own") == "deny"
    assert expected_for(e, "asha", "households", "select", "same_facility_other") == "deny"
    assert expected_for(e, "nurse", "medication_orders", "update", "own") == "deny"
    assert expected_for(e, "physician", "medication_orders", "update", "own") == "allow"
    assert expected_for(e, "pharmacist", "medication_orders", "select", "own") == "deny"
    assert expected_for(e, "pharmacist", "pharmacist_orders_v", "select", "own") == "allow"
    assert expected_for(e, "researcher", "research_export", "select", "none") == "deny"
    assert expected_for(e, "researcher", "patients", "select", "own") == "deny"
    for role in ROLES:
        for res in RESOURCES:
            for own in OWNERSHIPS:
                assert expected_for(e, role, res, "delete", own) == "deny"
            assert expected_for(e, role, "audit_log", "update", "own") == "deny"


def test_yaml_unknown_names_rejected(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "version: 1\ndefault: deny\nroles:\n  nurse:\n    patiens: {select: [own]}\nattacks: {}\n"
    )
    with pytest.raises(ValueError):
        load_expected(p)
