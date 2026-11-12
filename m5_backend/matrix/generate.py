"""Generate E5 access cases (access_case.v1) from the HAND-WRITTEN expected table.

The expected table (m5_backend/tests/access_matrix_expected.yaml) is the only source of the
`expected` field. Nothing here reads the SQL policies. Each case carries a `probe` (kept
outside the access_case.v1 document) that tells the runner HOW to try the access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from m5_backend.app.directory import load_directory

ROLES = ("asha", "nurse", "physician", "pharmacist", "researcher")
RESOURCES = (
    "facilities",
    "users",
    "households",
    "patients",
    "encounters",
    "records",
    "medication_orders",
    "consents",
    "audit_log",
    "research_export",
    "pharmacist_orders_v",
    "audio",
)
ACTIONS = ("select", "insert", "update", "delete")
OWNERSHIPS = ("own", "same_facility_other", "other_facility", "none")
ACTOR_KEYS = {
    "asha": "A1",
    "nurse": "N1",
    "physician": "P1",
    "pharmacist": "Ph1",
    "researcher": "R1",
}
DEFAULT_EXPECTED = Path(__file__).resolve().parents[1] / "tests" / "access_matrix_expected.yaml"

SQLI = (
    "' OR '1'='1",
    "'; DROP TABLE clinic.patients; --",
    "1; SELECT pg_sleep(0); --",
    "') OR 1=1 --",
    '" OR ""="',
    "'; RESET ROLE; SET ROLE physician_role; --",
    "x' UNION SELECT id FROM clinic.users --",
    "%' OR '%'='",
)

# Per role: endpoints the role IS allowed to use with a valid token (so a deny under a bad
# token proves the token, not the rule, was refused). Placeholders are resolved by the runner.
ROLE_ENDPOINTS: dict[str, list[tuple[str, str, str, str]]] = {
    "asha": [
        ("households", "GET", "/households", "own"),
        ("patients", "GET", "/patients/{patients.own}", "own"),
        ("records", "GET", "/records/{records.own}", "own"),
    ],
    "nurse": [
        ("patients", "GET", "/patients/{patients.own}", "own"),
        ("records", "GET", "/records/{records.own}", "own"),
        ("medication_orders", "GET", "/medication-orders/{medication_orders.own}", "own"),
    ],
    "physician": [
        ("patients", "GET", "/patients/{patients.own}", "own"),
        ("records", "GET", "/records/{records.own}", "own"),
        ("medication_orders", "GET", "/medication-orders/{medication_orders.own}", "own"),
    ],
    "pharmacist": [("pharmacist_orders_v", "POST", "/pharmacist/active-patient", "own")],
    "researcher": [("research_export", "GET", "/research/encounters", "own")],
}
# Phase C endpoints. access_case.v1 has a fixed resource enum, so they use resource "records";
# the tag keeps case ids unique.
EXTRA_TOKEN_ENDPOINTS: dict[str, list[tuple[str, str, str, str, str]]] = {
    r: [
        ("records_list", "records", "GET", "/records", "own"),
        ("transcript", "records", "GET", "/records/{records.own}/transcript", "own"),
    ]
    for r in ("asha", "nurse", "physician")
}
TOKEN_VARIANTS = {
    "tampered_jwt": (
        "payload_role_escalation",
        "payload_sub_swap",
        "signature_flip",
        "wrong_key",
        "foreign_issuer",
        "strip_signature",
    ),
    "expired_jwt": ("exp_minus_5s", "exp_minus_1d"),
    "alg_none": ("none", "None", "NONE"),
    "wrong_aud": ("other_aud", "aud_list_without_ours"),
}


@dataclass
class Case:
    case: dict[str, Any]
    probe: dict[str, Any] = field(default_factory=dict)


def load_expected(path: Path = DEFAULT_EXPECTED) -> dict[str, Any]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if doc.get("default") != "deny":
        raise ValueError("expected table must be default deny")
    for role, resources in (doc.get("roles") or {}).items():
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        for res, acts in (resources or {}).items():
            if res not in RESOURCES:
                raise ValueError(f"unknown resource {res!r} for {role}")
            for act, owns in (acts or {}).items():
                if act not in ACTIONS:
                    raise ValueError(f"unknown action {act!r}")
                for o in owns:
                    if o not in OWNERSHIPS:
                        raise ValueError(f"unknown ownership {o!r}")
    return doc


def expected_for(exp: dict[str, Any], role: str, resource: str, action: str, ownership: str) -> str:
    allowed = (((exp.get("roles") or {}).get(role) or {}).get(resource) or {}).get(action) or []
    return "allow" if ownership in allowed else "deny"


def endpoint_expected(exp: dict[str, Any], ep: str, role: str, action: str, ownership: str) -> str:
    allowed = (((exp.get("endpoints") or {}).get(ep) or {}).get(role) or {}).get(action) or []
    return "allow" if ownership in allowed else "deny"


def _attack_expected(exp: dict[str, Any], attack: str, sub: str | None = None) -> str:
    v = exp["attacks"][attack]
    if isinstance(v, dict):
        v = v[sub]
    if v not in ("allow", "deny"):
        raise ValueError(f"attack {attack}/{sub} expectation {v!r} needs the base rule")
    return v


def _case(cid, role, uid, resource, action, ownership, attack, expected) -> dict[str, Any]:
    return {
        "schema_version": "access_case.v1",
        "case_id": cid,
        "role": role,
        "user_id": uid,
        "resource": resource,
        "action": action,
        "ownership": ownership,
        "attack": attack,
        "expected": expected,
    }


def all_cases(exp: dict[str, Any]) -> list[Case]:
    d = load_directory()
    uid = {r: str(d.by_key(k).id) for r, k in ACTOR_KEYS.items()}
    out: list[Case] = []

    # 1) base cross product: 5 x 12 x 4 x 4
    for role in ROLES:
        for res in RESOURCES:
            for act in ACTIONS:
                for own in OWNERSHIPS:
                    out.append(
                        Case(
                            _case(f"base.{role}.{res}.{act}.{own}", role, uid[role], res, act, own,
                                  None, expected_for(exp, role, res, act, own)),
                            {"kind": "api_base_audio" if res == "audio" else "db_base"},
                        )
                    )  # fmt: skip

    # 2) token attacks on endpoints the role may normally use
    for attack, variants in TOKEN_VARIANTS.items():
        e = _attack_expected(exp, attack)
        for role in ROLES:
            eps = [(res, res, m, pa, o) for res, m, pa, o in ROLE_ENDPOINTS[role]]
            eps += EXTRA_TOKEN_ENDPOINTS.get(role, [])
            for tag, res, method, path, own in eps:
                for v in variants:
                    out.append(
                        Case(
                            _case(f"atk.{attack}.{role}.{tag}.{method.lower()}.{v}", role, uid[role],
                                  res, "select", own, attack, e),
                            {"kind": "api_token", "variant": v, "method": method, "path": path},
                        )
                    )  # fmt: skip

    # 3) id guessing on every id-addressed endpoint
    id_paths = {
        "patients": "/patients/{x}",
        "encounters": "/encounters/{x}",
        "records": "/records/{x}",
        "medication_orders": "/medication-orders/{x}",
        "audio": "/encounters/{x}/audio",
    }
    guesses = {
        "random_uuid4": "{random}",
        "nil_uuid": "00000000-0000-0000-0000-000000000000",
        "low_sequential": "00000000-0000-4000-8000-000000000001",
        "integer_1": "1",
    }
    e = _attack_expected(exp, "id_guess")
    for role in ROLES:
        for res, path in id_paths.items():
            for gname, gval in guesses.items():
                out.append(
                    Case(
                        _case(f"atk.id_guess.{role}.{res}.{gname}", role, uid[role], res, "select",
                              "none", "id_guess", e),
                        {"kind": "api_get", "path": path.replace("{x}", gval)},
                    )
                )  # fmt: skip

    # 4) SQL injection strings in every kind of text parameter
    for role in ROLES:
        for i, s in enumerate(SQLI):
            out.append(
                Case(
                    _case(
                        f"atk.sqli.id_param.{role}.{i}",
                        role,
                        uid[role],
                        "patients",
                        "select",
                        "none",
                        "sqli",
                        _attack_expected(exp, "sqli", "id_param"),
                    ),
                    {
                        "kind": "api_get",
                        "path": "/patients/{raw}",
                        "raw": s,
                        "param_kind": "id_param",
                    },
                )
            )
            out.append(
                Case(
                    _case(
                        f"atk.sqli.query_param.{role}.{i}",
                        role,
                        uid[role],
                        "patients",
                        "select",
                        "none",
                        "sqli",
                        _attack_expected(exp, "sqli", "query_param"),
                    ),
                    {
                        "kind": "api_get",
                        "path": "/patients",
                        "query": {"household_id": s},
                        "param_kind": "query_param",
                    },
                )
            )
            out.append(
                Case(
                    _case(
                        f"atk.sqli.text_field.{role}.{i}",
                        role,
                        uid[role],
                        "records",
                        "update",
                        "own",
                        "sqli",
                        expected_for(exp, role, "records", "update", "own"),
                    ),
                    {"kind": "api_sqli_text", "sqli": s, "param_kind": "text_field"},
                )
            )
            out.append(
                Case(
                    _case(
                        f"atk.sqli.constrained_field.{role}.encounter_type.{i}",
                        role,
                        uid[role],
                        "encounters",
                        "insert",
                        "own",
                        "sqli",
                        _attack_expected(exp, "sqli", "constrained_field"),
                    ),
                    {
                        "kind": "api_post",
                        "path": "/encounters",
                        "body": {"patient_id": "{patients.own}", "encounter_type": s},
                        "param_kind": "constrained_field",
                    },
                )
            )
    for i, s in enumerate(SQLI):
        out.append(
            Case(
                _case(
                    f"atk.sqli.constrained_field.physician.drug.{i}",
                    "physician",
                    uid["physician"],
                    "medication_orders",
                    "insert",
                    "own",
                    "sqli",
                    _attack_expected(exp, "sqli", "constrained_field"),
                ),
                {
                    "kind": "api_post",
                    "path": "/medication-orders",
                    "body": {
                        "encounter_id": "{encounters.own}",
                        "drug": s,
                        "dose_value": 500,
                        "dose_unit": "mg",
                        "frequency_per_day": 3,
                        "duration_days": 3,
                    },
                    "param_kind": "constrained_field",
                },
            )
        )
        out.append(
            Case(
                _case(
                    f"atk.sqli.constrained_field.nurse.name.{i}",
                    "nurse",
                    uid["nurse"],
                    "patients",
                    "insert",
                    "own",
                    "sqli",
                    _attack_expected(exp, "sqli", "constrained_field"),
                ),
                {
                    "kind": "api_post",
                    "path": "/patients",
                    "body": {
                        "household_id": "{households.own}",
                        "name_synthetic": "SYNTHETIC-" + s,
                        "age_band": "25-34",
                        "sex": "F",
                    },
                    "param_kind": "constrained_field",
                },
            )
        )
        for fld in ("username", "password"):
            role = ROLES[i % len(ROLES)]
            out.append(Case(
                _case(f"atk.sqli.login_field.{fld}.{i}", role, uid[role], "users", "select", "none",
                      "sqli", _attack_expected(exp, "sqli", "login_field")),
                {"kind": "api_login", "field": fld, "sqli": s, "param_kind": "login_field"}))  # fmt: skip

    # 5) mass assignment: forbidden server-owned fields in request bodies
    e = _attack_expected(exp, "mass_assignment")
    mass = [
        ("asha", "households", "insert", "/households", {"assigned_asha_id": "{users.A2}"}),
        ("asha", "households", "insert", "/households", {"facility_id": "{facilities.F2}"}),
        ("asha", "households", "insert", "/households", {"role": "physician"}),
        ("asha", "patients", "insert", "/patients",
         {"household_id": "{households.own}", "name_synthetic": "SYNTHETIC-Mass-A", "age_band": "25-34",
          "sex": "F", "facility_id": "{facilities.F2}"}),
        ("asha", "encounters", "insert", "/encounters",
         {"patient_id": "{patients.own}", "encounter_type": "asha_household_visit", "author_id": "{users.A2}"}),
        ("nurse", "encounters", "insert", "/encounters",
         {"patient_id": "{patients.own}", "encounter_type": "nurse_consult", "author_id": "{users.N2}"}),
        ("nurse", "encounters", "insert", "/encounters",
         {"patient_id": "{patients.own}", "encounter_type": "nurse_consult", "facility_id": "{facilities.F2}"}),
        ("nurse", "encounters", "insert", "/encounters",
         {"patient_id": "{patients.own}", "encounter_type": "nurse_consult", "role": "physician"}),
        ("nurse", "records", "update", "PATCH /records/{records.own}", {"record": "{record_json}", "status": "saved"}),
        ("nurse", "records", "update", "PATCH /records/{records.own}", {"record": "{record_json}", "approved_by": "{users.N1}"}),
        ("nurse", "records", "update", "PATCH /records/{records.own}", {"record": "{record_json}", "approved_at": "2026-11-09T00:00:00Z"}),
        ("nurse", "patients", "update", "PATCH /patients/{patients.own}", {"age_band": "25-34", "facility_id": "{facilities.F2}"}),
        ("physician", "medication_orders", "insert", "/medication-orders",
         {"encounter_id": "{encounters.own}", "drug": "paracetamol", "dose_value": 500, "dose_unit": "mg",
          "frequency_per_day": 3, "duration_days": 3, "facility_id": "{facilities.F2}"}),
        ("physician", "medication_orders", "insert", "/medication-orders",
         {"encounter_id": "{encounters.own}", "drug": "paracetamol", "dose_value": 500, "dose_unit": "mg",
          "frequency_per_day": 3, "duration_days": 3, "patient_id": "{patients.other_facility}"}),
        ("physician", "medication_orders", "update", "PATCH /medication-orders/{medication_orders.own}",
         {"dose_value": 250, "facility_id": "{facilities.F2}"}),
        ("physician", "records", "update", "PATCH /records/{records.own}", {"record": "{record_json}", "approved_by": "{users.P2}"}),
        ("pharmacist", "pharmacist_orders_v", "select", "/pharmacist/active-patient",
         {"patient_id": "{patients.own}", "facility_id": "{facilities.F2}"}),
        ("pharmacist", "pharmacist_orders_v", "select", "/pharmacist/active-patient",
         {"patient_id": "{patients.own}", "role": "physician"}),
        ("researcher", "users", "select", "/auth/token",
         {"username": "{users.R1}", "password": "{mock_password}", "role": "physician"}),
        ("researcher", "users", "select", "/auth/token",
         {"username": "{users.R1}", "password": "{mock_password}", "facility_id": "{facilities.F2}"}),
    ]  # fmt: skip
    for i, (role, res, act, target, body) in enumerate(mass):
        method, path = target.split(" ", 1) if " " in target else ("POST", target)
        out.append(Case(
            _case(f"atk.mass_assignment.{role}.{res}.{i}", role, uid[role], res, act, "own",
                  "mass_assignment", e),
            {"kind": "api_mass", "method": method, "path": path, "body": body}))  # fmt: skip

    # 5b) saved-gate attacks (F1 / D-80): the server owns the verdict; a save needs one
    #     resolution per stored flag from the approving physician. Every case expects deny
    #     (hand-written in access_matrix_expected.yaml: attacks.save_gate).
    e = _attack_expected(exp, "save_gate")
    save_gate = [
        # (acting role, variant, attack label, ownership)
        ("physician", "forged_verdict", "mass_assignment", "own"),
        ("physician", "nonexistent_flag", "mass_assignment", "own"),
        ("physician", "missing_resolution", "mass_assignment", "own"),
        ("physician", "duplicate_resolution", "mass_assignment", "own"),
        ("physician", "resolution_by_other_user", "mass_assignment", "own"),
        ("physician", "stale_after_change", "mass_assignment", "own"),
        ("physician", "unknown_verdict_id", "id_guess", "none"),
        ("physician", "verdict_of_other_record", "id_guess", "own"),
        ("physician", "cross_facility", "id_guess", "other_facility"),
        ("nurse", "non_physician_resolves", "mass_assignment", "own"),
        ("asha", "non_physician_resolves", "mass_assignment", "own"),
        ("pharmacist", "non_physician_resolves", "mass_assignment", "own"),
        ("researcher", "non_physician_resolves", "mass_assignment", "own"),
    ]
    for role, variant, atk, own in save_gate:
        out.append(Case(
            _case(f"atk.{atk}.save_gate.{role}.{variant}", role, uid[role], "records", "update", own,
                  atk, e),
            {"kind": "api_save_gate", "variant": variant}))  # fmt: skip

    # 5b) Phase C endpoints: GET /records (list) and GET /records/{id}/transcript.
    #     Expected comes from the hand-written `endpoints` section of the expected table.
    for ep in ("records_list", "transcript"):
        for role in ROLES:
            for act in ACTIONS:
                for own in OWNERSHIPS:
                    out.append(Case(
                        _case(f"ep.{ep}.{role}.{act}.{own}", role, uid[role], "records", act, own,
                              None, endpoint_expected(exp, ep, role, act, own)),
                        {"kind": "api_ep_" + ep}))  # fmt: skip
    e = _attack_expected(exp, "id_guess")
    for role in ROLES:
        for gname, gval in guesses.items():
            out.append(Case(
                _case(f"atk.id_guess.{role}.transcript.{gname}", role, uid[role], "records",
                      "select", "none", "id_guess", e),
                {"kind": "api_get", "path": f"/records/{gval}/transcript"}))  # fmt: skip

    # 6) IDOR on audio files
    e = _attack_expected(exp, "idor_audio")
    audio = []
    for role in ROLES:
        audio.append((role, "other_facility", "/encounters/{encounters.other_facility}/audio"))
        for _tname, t in (("dotdot_encoded", "..%2F..%2F.env"), ("dotdot_plain", "../../.env"),
                         ("dot_encoded", "%2e%2e%2f%2e%2e%2f.env")):  # fmt: skip
            audio.append((role, "none", "/encounters/" + t + "/audio"))
    audio += [
        ("asha", "same_facility_other", "/encounters/{encounters.same_facility_other}/audio"),
        ("asha", "none", "/encounters/{encounters.none}/audio"),
        ("pharmacist", "own", "/encounters/{encounters.own}/audio"),
        ("pharmacist", "same_facility_other", "/encounters/{encounters.same_facility_other}/audio"),
        ("researcher", "own", "/encounters/{encounters.own}/audio"),
        ("researcher", "same_facility_other", "/encounters/{encounters.same_facility_other}/audio"),
    ]
    for i, (role, own, path) in enumerate(audio):
        out.append(Case(
            _case(f"atk.idor_audio.{role}.{own}.{i}", role, uid[role], "audio", "select", own,
                  "idor_audio", e),
            {"kind": "api_get", "path": path, "raw_path": "{" not in path}))  # fmt: skip

    # 7) GUC / role tampering (DB session level + via the API)
    e = _attack_expected(exp, "guc_tamper")
    for role in ROLES:
        for v in ("reset_role_then_select", "set_role_owner", "set_role_bootstrap",
                  "set_session_authorization", "garbage_guc"):  # fmt: skip
            out.append(Case(
                _case(f"atk.guc_tamper.db.{role}.{v}", role, uid[role], "patients", "select", "own",
                      "guc_tamper", e),
                {"kind": "db_guc", "variant": v}))  # fmt: skip
        for v in ("header_user_id", "query_param_guc", "set_user_id_via_body_sql", "role_header"):
            out.append(Case(
                _case(f"atk.guc_tamper.api.{role}.{v}", role, uid[role], "patients", "select",
                      "other_facility", "guc_tamper", e),
                {"kind": "api_guc", "variant": v}))  # fmt: skip
    return out


def main() -> int:
    import json

    from contracts.validate import validate_doc

    cases = all_cases(load_expected())
    bad = [c.case["case_id"] for c in cases if validate_doc("access_case.v1", c.case)]
    out = Path(__file__).resolve().parents[2] / "results" / "m5_backend" / "access_cases.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for c in cases:
            fh.write(json.dumps(c.case, ensure_ascii=False) + "\n")
    print(f"generated {len(cases)} access_case.v1 cases -> {out.name}; invalid: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
