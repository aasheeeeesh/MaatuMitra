"""Run the E5 access matrix against a real PostgreSQL 16 (+ the FastAPI app in-process).

Base cases run at the DATABASE level through the same `Database.request_tx` the API uses
(SET LOCAL ROLE + transaction-local GUCs), each in its own transaction that is ROLLED BACK.
Audio and attack cases run through the API (FastAPI TestClient against the real DB).

"allow" is observed when the statement/request succeeds AND touches/returns >= 1 row
(HTTP 2xx for API cases). Errors, 0 rows, 401/403/404/405/409/422/429 are "deny".
This module only resolves WHICH row a case targets (from the seed); the expected outcome
always comes from the hand-written table via generate.py.

    uv run python -m m5_backend.matrix.run      (needs the DB from db_up.sh)
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

import jwt
import psycopg
from psycopg import sql

from contracts.validate import validate_doc
from m5_backend.app.auth import Principal, issue_token
from m5_backend.app.export import hmac_key_bytes, pseudonym

from .generate import ACTOR_KEYS, Case, all_cases, load_expected

RESULTS = Path(__file__).resolve().parents[2] / "results" / "m5_backend"
CHAIN = {"own": "A1", "same_facility_other": "A2", "other_facility": "A3", "none": "none"}
ENC = {  # role -> ownership -> encounter key in the seed
    "asha": {"own": "A1", "same_facility_other": "A2", "other_facility": "A3", "none": "none"},
    "nurse": {"own": "N1", "same_facility_other": "N2", "other_facility": "N3", "none": "none"},
    "physician": {
        "own": "P1",
        "same_facility_other": "P2",
        "other_facility": "P3",
        "none": "none_p",
    },
}
ENC["pharmacist"] = ENC["researcher"] = ENC["nurse"]
COLLEAGUE = {"asha": "A2", "nurse": "N2", "physician": "P2", "pharmacist": "A2", "researcher": "A2"}
F2_PEER = {"asha": "A3", "nurse": "N3", "physician": "P3", "pharmacist": "Ph2", "researcher": "A3"}
ETYPE = {
    "asha": "asha_household_visit",
    "nurse": "nurse_consult",
    "physician": "physician_consult",
    "pharmacist": "pharmacist_dispensing",
    "researcher": "nurse_consult",
}
TABLE = {
    "facilities": ("clinic.facilities", "id", "name"),
    "users": ("clinic.users", "id", "display_name"),
    "households": ("clinic.households", "id", "assigned_asha_id"),
    "patients": ("clinic.patients", "id", "age_band"),
    "encounters": ("clinic.encounters", "id", "encounter_type"),
    "records": ("clinic.records", "id", "json"),
    "medication_orders": ("clinic.medication_orders", "id", "dose_value"),
    "consents": ("clinic.consents", "patient_id", "research_ok"),
    "audit_log": ("clinic.audit_log", "id", "outcome"),
    "research_export": ("research.encounters_deid", "pseudonym", "age_band"),
    "pharmacist_orders_v": ("clinic.pharmacist_orders_v", "order_id", "status"),
}


def _b64(obj: Any) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )


class Runner:
    def __init__(self, env):
        from fastapi.testclient import TestClient

        from m5_backend.app.main import create_app

        self.env = env
        self.s = env.settings
        self.ids = env.seed
        self.d = env.directory
        # own app instance -> own rate-limiter state
        self.client = TestClient(
            create_app(self.s, env.api_db, directory=self.d, audio_dir=env.audio_dir)
        )
        self.key = hmac_key_bytes(self.s)
        self.actor = {r: self.d.by_key(k) for r, k in ACTOR_KEYS.items()}

    # ---------------------------------------------------------------- targets
    def principal(self, role: str) -> Principal:
        u = self.actor[role]
        return Principal(u.id, u.role, u.facility_id)

    def target(self, role: str, res: str, own: str) -> Any:
        ids, chain = self.ids, CHAIN[own]
        if res == "facilities":
            return ids.facilities[
                {"own": "F1", "same_facility_other": "F1", "other_facility": "F2", "none": "F3"}[
                    own
                ]
            ]
        if res == "users":
            return {"own": self.actor[role].id, "same_facility_other": ids.users[COLLEAGUE[role]],
                    "other_facility": ids.users[F2_PEER[role]], "none": ids.users["P2"]}[own]  # fmt: skip
        if res == "households":
            return ids.households[chain]
        if res in ("patients", "consents"):
            return ids.patients[chain]
        if res in ("encounters", "audio"):
            return ids.encounters[ENC[role][own]]
        if res == "records":
            return ids.records[ENC[role][own]]
        if res in ("medication_orders", "pharmacist_orders_v"):
            if role == "pharmacist" and own == "none":
                return ids.orders["P1_draft"]  # active patient's order that is NOT ready
            return ids.orders[
                {"own": "P1", "same_facility_other": "P2", "other_facility": "P3", "none": "none"}[
                    own
                ]
            ]
        if res == "audit_log":
            key = {"own": ACTOR_KEYS[role], "same_facility_other": COLLEAGUE[role],
                   "other_facility": F2_PEER[role], "none": "none"}[own]  # fmt: skip
            return ids.audit[key]
        if res == "research_export":
            return pseudonym(self.key, ids.patients[chain])
        raise KeyError(res)

    def active_patient(self, role: str, own: str) -> uuid.UUID | None:
        if role != "pharmacist":
            return None
        return self.ids.patients["A3" if own == "other_facility" else "A1"]

    def resolve(self, role: str, v: Any) -> Any:
        if isinstance(v, dict):
            return {k: self.resolve(role, x) for k, x in v.items()}
        if not isinstance(v, str) or "{" not in v:
            return v
        out = v
        while "{" in out:
            a = out.index("{")
            b = out.index("}", a)
            tok = out[a + 1 : b]
            if tok == "record_json":
                return self.valid_record(role)
            if tok == "random":
                val = str(uuid.uuid4())
            elif tok == "mock_password":
                val = self.s.mock_login_password
            elif "." in tok:
                kind, name = tok.split(".", 1)
                if kind == "users":
                    val = str(self.ids.users[name])
                elif kind == "facilities":
                    val = str(self.ids.facilities[name])
                elif kind == "medication_orders":
                    val = str(self.target(role, "medication_orders", name))
                else:
                    val = str(self.target(role, kind, name))
            else:
                raise KeyError(tok)
            out = out[:a] + val + out[b + 1 :]
        return out

    def valid_record(self, role: str, advice_text: str | None = None) -> dict:
        rec = json.loads(json.dumps(self.ids.record_json[ENC[role]["own"]]))
        rec["status"] = "draft"
        if advice_text is not None:
            rec["advice"] = [*rec.get("advice", []), {
                "text": advice_text, "negated": False,
                "evidence": {"span_text": "x", "char_start": 0, "char_end": 1,
                             "audio_start": None, "audio_end": None}}]  # fmt: skip
        return rec

    # ---------------------------------------------------------------- DB-level cases
    def db_base(self, c: dict) -> tuple[str, str]:
        role, res, act, own = c["role"], c["resource"], c["action"], c["ownership"]
        tbl, key, col = TABLE[res]
        t = self.target(role, res, own)
        a = self.actor[role]
        ti, ki, ci = sql.Identifier(*tbl.split(".")), sql.Identifier(key), sql.Identifier(col)
        if act == "select":
            q, args = sql.SQL("SELECT 1 FROM {} WHERE {} = %s").format(ti, ki), (t,)
        elif act == "update":
            q, args = sql.SQL("UPDATE {} SET {} = {} WHERE {} = %s").format(ti, ci, ci, ki), (t,)
        elif act == "delete":
            q, args = sql.SQL("DELETE FROM {} WHERE {} = %s").format(ti, ki), (t,)
        else:
            q, args = self.insert_stmt(role, res, own, a)
        try:
            with self.env.api_db.request_tx(
                self.principal(role), active_patient_id=self.active_patient(role, own), commit=False
            ) as cur:
                cur.execute(q, args)
                n = cur.rowcount
            return ("allow" if n >= 1 else "deny"), f"rows={n}"
        except psycopg.Error as exc:
            return "deny", f"sqlstate={exc.sqlstate}"

    def insert_stmt(self, role, res, own, a) -> tuple[str, tuple]:
        ids, chain = self.ids, CHAIN[own]
        fac_of = {"A1": ids.facilities["F1"], "A2": ids.facilities["F1"], "A3": ids.facilities["F2"],
                  "none": ids.facilities["F1"]}  # fmt: skip
        if res == "facilities":
            return "INSERT INTO clinic.facilities (name) VALUES ('SYNTHETIC-PHC-matrix')", ()
        if res == "users":
            return ("INSERT INTO clinic.users (role, facility_id, display_name) VALUES ('nurse', %s, 'SYNTHETIC-U')",
                    (self.target(role, "facilities", own),))  # fmt: skip
        if res == "households":
            asha = {"own": a.id if role == "asha" else ids.users["A1"], "same_facility_other": ids.users["A2"],
                    "other_facility": ids.users["A3"], "none": None}[own]  # fmt: skip
            return ("INSERT INTO clinic.households (facility_id, assigned_asha_id) VALUES (%s, %s)",
                    (fac_of[chain], asha))  # fmt: skip
        if res == "patients":
            return ("INSERT INTO clinic.patients (household_id, facility_id, name_synthetic, age_band, sex)"
                    " VALUES (%s, %s, 'SYNTHETIC-Matrix-Insert', '25-34', 'F')",
                    (ids.households[chain], fac_of[chain]))  # fmt: skip
        if res == "encounters":
            return ("INSERT INTO clinic.encounters (patient_id, author_id, facility_id, encounter_type)"
                    " VALUES (%s, %s, %s, %s)", (ids.patients[chain], a.id, fac_of[chain], ETYPE[role]))  # fmt: skip
        if res == "records":
            return ("INSERT INTO clinic.records (encounter_id, json, status) VALUES (%s, '{\"matrix\": true}', 'draft')",
                    (self.target(role, "encounters", own),))  # fmt: skip
        if res == "medication_orders":
            ek = ENC["physician"][own]
            return ("INSERT INTO clinic.medication_orders (encounter_id, patient_id, facility_id, drug, dose_value,"
                    " dose_unit, frequency_per_day, duration_days, status)"
                    " VALUES (%s, %s, %s, 'paracetamol', 500, 'mg', 3, 3, 'draft')",
                    (ids.encounters[ek], ids.patients[chain], fac_of[chain]))  # fmt: skip
        if res == "consents":
            return ("INSERT INTO clinic.consents (patient_id, research_ok) VALUES (%s, false)",
                    (ids.patients[chain + "b"],))  # fmt: skip
        if res == "audit_log":
            return ("INSERT INTO clinic.audit_log (user_id, app_role, action, table_name, outcome)"
                    " VALUES (%s, %s, 'select', 'patients', 'allow')",
                    (self.target(role, "users", own), role))  # fmt: skip
        if res == "research_export":
            return ("INSERT INTO research.encounters_deid (pseudonym, age_band, sex, encounter_type, encounter_month)"
                    " VALUES (%s, '25-34', 'F', 'nurse_consult', '2026-10')", (self.target(role, res, own),))  # fmt: skip
        if res == "pharmacist_orders_v":
            return ("INSERT INTO clinic.pharmacist_orders_v (drug, dose_value, dose_unit, frequency_per_day,"
                    " duration_days, status) VALUES ('paracetamol', 500, 'mg', 3, 3, 'ready_to_dispense')", ())  # fmt: skip
        raise KeyError(res)

    def db_guc(self, c: dict, variant: str) -> tuple[str, str]:
        role = c["role"]
        t = self.target(role, "patients", "own")
        boot = self.s.bootstrap_user or "postgres"
        pre = {
            "reset_role_then_select": [("RESET ROLE", ())],
            "set_role_owner": [("SET LOCAL ROLE owner_role", ())],
            "set_role_bootstrap": [(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(boot)), ())],
            "set_session_authorization": [("SET SESSION AUTHORIZATION owner_role", ())],
            "garbage_guc": [("SELECT set_config('app.user_id', %s, true), set_config('app.facility_id', %s, true)",
                             ("x' OR '1'='1", "x' OR '1'='1"))],
        }[variant]  # fmt: skip
        try:
            with self.env.api_db.request_tx(self.principal(role), commit=False) as cur:
                for q, args in pre:
                    cur.execute(q, args)
                cur.execute("SELECT 1 FROM clinic.patients WHERE id = %s", (t,))
                n = len(cur.fetchall())
            return ("allow" if n >= 1 else "deny"), f"rows={n}"
        except psycopg.Error as exc:
            return "deny", f"sqlstate={exc.sqlstate}"

    # ---------------------------------------------------------------- API-level cases
    def token(self, role: str) -> str:
        return issue_token(self.s, self.actor[role])

    def bad_token(self, role: str, attack: str, variant: str) -> str:
        s, u = self.s, self.actor[role]
        good = issue_token(s, u)
        h, p, sig = good.split(".")
        claims = jwt.decode(good, options={"verify_signature": False})
        k = s.jwt_signing_key
        if variant == "payload_role_escalation":
            # Bug found 2026-11-10: escalating a physician "to physician" left the token genuine.
            esc = "physician" if role != "physician" else "nurse"
            assert esc != claims["role"], "probe must really change the role claim"
            return f"{h}.{_b64({**claims, 'role': esc})}.{sig}"
        if variant == "payload_sub_swap":
            new_sub = str(self.ids.users[F2_PEER[role]])
            assert new_sub != claims["sub"], "probe must really change the sub claim"
            return f"{h}.{_b64({**claims, 'sub': new_sub})}.{sig}"
        if variant == "signature_flip":
            return f"{h}.{p}.{('A' if sig[0] != 'A' else 'B') + sig[1:]}"
        if variant == "wrong_key":
            return jwt.encode(claims, "f" * 64, algorithm="HS256")
        if variant == "foreign_issuer":
            return jwt.encode({**claims, "iss": "evil-issuer"}, "e" * 64, algorithm="HS256")
        if variant == "strip_signature":
            return f"{h}.{p}."
        if variant == "exp_minus_5s":
            return issue_token(s, u, now=time.time() - s.jwt_ttl_seconds - 5)
        if variant == "exp_minus_1d":
            return issue_token(s, u, now=time.time() - 86400)
        if attack == "alg_none":
            return f"{_b64({'alg': variant, 'typ': 'JWT'})}.{p}."
        if variant == "other_aud":
            return jwt.encode({**claims, "aud": "another-api"}, k, algorithm="HS256")
        if variant == "aud_list_without_ours":
            return jwt.encode({**claims, "aud": ["another-api", "third-api"]}, k, algorithm="HS256")
        raise KeyError(variant)

    def call(self, role, method, path, body=None, token=None, headers=None, params=None):
        hdr = {"Authorization": f"Bearer {token or self.token(role)}", **(headers or {})}
        return self.client.request(method, path, json=body, headers=hdr, params=params)

    def api_case(self, case: Case) -> tuple[str, str]:
        c, pr = case.case, case.probe
        role, kind = c["role"], pr["kind"]
        ok = lambda r: ("allow" if 200 <= r.status_code < 300 else "deny", f"http={r.status_code}")  # noqa: E731
        if kind == "api_base_audio":
            path = f"/encounters/{self.target(role, 'audio', c['ownership'])}/audio"
            method = {"select": "GET", "insert": "PUT", "update": "PATCH", "delete": "DELETE"}[
                c["action"]
            ]
            return ok(self.call(role, method, path))
        if kind == "api_token":
            path = self.resolve(role, pr["path"])
            body = (
                {"patient_id": str(self.target(role, "patients", "own"))}
                if pr["method"] == "POST"
                else None
            )
            control = self.call(role, pr["method"], path, body)
            r = self.call(
                role,
                pr["method"],
                path,
                body,
                token=self.bad_token(role, c["attack"], pr["variant"]),
            )
            obs, det = ok(r)
            return obs, det + f";control={control.status_code}"
        if kind == "api_get":
            if "raw" in pr:
                path = pr["path"].replace("{raw}", quote(pr["raw"], safe=""))
            elif pr.get("raw_path"):
                path = pr["path"]
            else:
                path = self.resolve(role, pr["path"])
            return ok(self.call(role, "GET", path, params=pr.get("query")))
        if kind == "api_post":
            return ok(self.call(role, "POST", pr["path"], self.resolve(role, pr["body"])))
        if kind == "api_mass":
            path = self.resolve(role, pr["path"])
            body = self.resolve(role, pr["body"])
            if path == "/auth/token":
                r = self.client.post(path, json=body)
            else:
                r = self.call(role, pr["method"], path, body)
            return ok(r)
        if kind == "api_login":
            body = {"username": str(self.actor[role].id), "password": self.s.mock_login_password}
            body[pr["field"]] = pr["sqli"]
            return ok(self.client.post("/auth/token", json=body))
        if kind == "api_sqli_text":
            rid = self.target(role, "records", "own")
            r = self.call(
                role, "PATCH", f"/records/{rid}", {"record": self.valid_record(role, pr["sqli"])}
            )
            obs, det = ok(r)
            if obs == "allow":  # stored literally? read back as the same user
                back = self.call(role, "GET", f"/records/{rid}").json()
                if back["json"]["advice"][-1]["text"] != pr["sqli"]:
                    return "integrity_fail", det + ";readback_mismatch"
                det += ";readback_identical"
            return obs, det
        if kind == "api_guc":
            v = pr["variant"]
            target = f"/patients/{self.target(role, 'patients', 'other_facility')}"
            peer = str(self.ids.users[F2_PEER[role]])
            f2 = str(self.ids.facilities["F2"])
            if v == "header_user_id":
                r = self.call(
                    role, "GET", target, headers={"X-App-User-Id": peer, "X-App-Facility-Id": f2}
                )
            elif v == "query_param_guc":
                r = self.call(
                    role, "GET", target, params={"app.user_id": peer, "app.facility_id": f2}
                )
            elif v == "set_user_id_via_body_sql":
                inj = f"x'); SELECT set_config('app.facility_id', '{f2}', false); RESET ROLE; --"
                rid = self.target(role, "records", "own")
                self.call(
                    role, "PATCH", f"/records/{rid}", {"record": self.valid_record(role, inj)}
                )
                r = self.call(role, "GET", target)
            else:  # role_header
                r = self.call(
                    role,
                    "GET",
                    target,
                    headers={"X-Role": "physician", "X-Postgres-Role": "owner_role"},
                )
            return ok(r)
        raise KeyError(kind)

    # ---------------------------------------------------------------- driver
    def run_case(self, case: Case) -> dict[str, Any]:
        c, kind = case.case, case.probe["kind"]
        if kind == "db_base":
            layer, (obs, det) = "db", self.db_base(c)
        elif kind == "db_guc":
            layer, (obs, det) = "db", self.db_guc(c, case.probe["variant"])
        else:
            layer, (obs, det) = "api", self.api_case(case)
        if obs == "integrity_fail":
            outcome = "integrity_fail"
        elif obs == c["expected"]:
            outcome = "pass"
        elif c["expected"] == "deny":
            outcome = "unauthorized_success"
        else:
            outcome = "unexpected_denial"
        return {"case": c, "layer": layer, "observed": obs, "outcome": outcome, "detail": det}


def run_matrix(env, expected_path: Path | None = None, write: bool = True) -> dict[str, Any]:
    exp = load_expected(expected_path) if expected_path else load_expected()
    cases = all_cases(exp)
    invalid = [c.case["case_id"] for c in cases if validate_doc("access_case.v1", c.case)]
    if invalid:
        raise ValueError(f"{len(invalid)} generated cases are not valid access_case.v1")
    env.export()  # research schema must reflect current consents
    runner = Runner(env)
    t0 = time.time()
    results = [
        runner.run_case(c) for c in sorted(cases, key=lambda c: c.probe["kind"] != "db_base")
    ]
    # integrity: the sqli strings must not have damaged anything
    with env.owner_conn() as oc, oc.transaction():
        oc.execute("SET LOCAL ROLE maint_role")
        n_pat = oc.execute("SELECT count(*) FROM clinic.patients").fetchone()[0]
    counts = Counter(r["outcome"] for r in results)
    n = len(results)
    n_deny = sum(1 for r in results if r["case"]["expected"] == "deny")
    summary = {
        "n_cases": n,
        "n_expected_deny": n_deny,
        "n_expected_allow": n - n_deny,
        "unauthorized_successes": counts.get("unauthorized_success", 0),
        "unexpected_denials": counts.get("unexpected_denial", 0),
        "integrity_failures": counts.get("integrity_fail", 0),
        "passes": counts.get("pass", 0),
        "patients_rows_after_run": n_pat,
        "by_attack": dict(Counter(str(r["case"]["attack"]) for r in results)),
        "by_layer": dict(Counter(r["layer"] for r in results)),
        "runtime_s": round(time.time() - t0, 1),
    }
    summary["line"] = (
        f"unauthorized successes: {summary['unauthorized_successes']} of {n_deny} deny-expected cases "
        f"({n} cases total); 95% upper bound (rule of three) 3/{n_deny} = {3 / n_deny:.4f}"
    )
    if write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        with (RESULTS / "access_matrix_results.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as fh:
            for r in results:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with (RESULTS / "access_cases.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for c in cases:
                fh.write(json.dumps(c.case, ensure_ascii=False) + "\n")
        (RESULTS / "access_matrix_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
    summary["failures"] = [r for r in results if r["outcome"] != "pass"]
    return summary


def main() -> int:
    import tempfile

    from m5_backend.app.config import load_settings
    from m5_backend.scripts.dbtool import prepare_test_database, probe

    s = load_settings()
    ok, why = probe(s)
    if not ok:
        print(f"needs_db: {why}")
        return 2
    env = prepare_test_database(s, "maatumitra_matrix", Path(tempfile.mkdtemp(prefix="m5_audio_")))
    summ = run_matrix(env)
    print(summ["line"])
    print(f"unexpected denials (availability bugs): {summ['unexpected_denials']}; "
          f"integrity failures: {summ['integrity_failures']}")  # fmt: skip
    for f in summ["failures"][:20]:
        print("  ", f["outcome"], f["case"]["case_id"], f["detail"])
    return 0 if not summ["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
