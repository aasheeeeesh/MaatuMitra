"""De-identification: scan the research export for every original id, name and free-text token."""

import json

import psycopg
import pytest
import regex

from m5_backend.app.export import SYMPTOM_VOCAB, UNIT_VOCAB, drug_vocab, hmac_key_bytes, pseudonym

pytestmark = pytest.mark.needs_db
TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")


def research_rows(client, env):
    from m5_backend.app.auth import issue_token

    tok = issue_token(env.settings, env.directory.by_key("R1"))
    r = client.get("/research/encounters", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    return r.json()


def originals(env):
    """Every original identifier, name, date and free-text token, read as maint_role."""
    ids, names, free = set(), set(), set()
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        for t in [
            "facilities",
            "users",
            "households",
            "patients",
            "encounters",
            "records",
            "medication_orders",
        ]:
            for (i,) in c.execute(f"SELECT id::text FROM clinic.{t}"):
                ids.update({i, i.replace("-", "")})
        for (n,) in c.execute("SELECT name_synthetic FROM clinic.patients UNION SELECT display_name FROM clinic.users"
                              " UNION SELECT name FROM clinic.facilities"):  # fmt: skip
            names.add(n)
            # name parts (e.g. the fake first name); random hex suffixes are skipped because a
            # 6-hex string can occur by chance inside a 20-hex pseudonym
            names.update(t for t in TOKEN.findall(n) if not regex.fullmatch(r"[0-9a-f]+", t))
        dates = {
            d
            for (d,) in c.execute("SELECT to_char(created_at, 'YYYY-MM-DD') FROM clinic.encounters")
        }
        for (j,) in c.execute("SELECT json FROM clinic.records"):
            for k in ("record_id", "patient_ref", "source_transcript_id"):
                if j.get(k):
                    ids.add(j[k])
            texts = [a["text"] for a in j.get("advice", [])]
            texts += [
                x["evidence"]["span_text"]
                for g in ("symptoms", "medications", "advice")
                for x in j.get(g, [])
            ]
            if j.get("follow_up"):
                texts += [j["follow_up"]["text"], j["follow_up"]["evidence"]["span_text"]]
            for t in texts:
                free.update(TOKEN.findall(t))
    return ids, names, dates, free


def test_export_contains_no_ids_names_dates_or_free_text(client, env):
    env.export()
    rows = research_rows(client, env)
    assert rows, "export is empty"
    blob = json.dumps(rows, ensure_ascii=False)
    ids, names, dates, free = originals(env)
    assert [i for i in ids if i in blob] == []
    assert [n for n in names if n in blob] == []
    assert [d for d in dates if d in blob] == []
    # free-text tokens: compare against tokens of STRING values in the export, minus the closed
    # structured vocabularies (a drug/symptom/unit name is allowed to also occur in free text)
    allowed = {t for w in SYMPTOM_VOCAB | UNIT_VOCAB | drug_vocab() for t in TOKEN.findall(w)}
    vals = set()
    for r in rows:
        for v in [r["age_band"], r["sex"], r["encounter_type"], r["encounter_month"], r["record_status"] or "",
                  *r["symptoms_present"], *r["symptoms_absent"],
                  *[m["drug"] for m in r["medications"]], *[m["dose_unit"] or "" for m in r["medications"]]]:  # fmt: skip
            vals.update(TOKEN.findall(v))
    leaked = sorted((free - allowed) & vals)
    assert leaked == [], leaked
    assert len(free - allowed) > 10  # the scan really had free text to look for
    for r in rows:
        assert set(r) == {"pseudonym", "age_band", "sex", "encounter_type", "encounter_month", "record_status",
                          "symptoms_present", "symptoms_absent", "medications"}  # fmt: skip
        assert regex.fullmatch(r"\d{4}-\d{2}", r["encounter_month"])


def test_only_consenting_patients_and_withdrawal_removes_rows(client, env):
    key, ids = hmac_key_bytes(env.settings), env.seed.patients
    env.export()
    ps = {r["pseudonym"] for r in research_rows(client, env)}
    for k in ("C1", "C2", "C3", "C4", "C5"):  # the k >= 5 cohort is exported
        assert pseudonym(key, ids[k]) in ps
    # consenting but alone in their cell -> suppressed by the small-cell rule (F3)
    for k in ("A1", "A2", "A3"):
        assert pseudonym(key, ids[k]) not in ps
    assert pseudonym(key, ids["none"]) not in ps  # research_ok = false
    assert pseudonym(key, ids["A1b"]) not in ps  # no consent row at all
    # withdrawal is immediate (F4 trigger): see test_hardening.py for the full check
    try:
        with env.owner_conn() as c, c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            c.execute(
                "UPDATE clinic.consents SET research_ok = false, updated_at = now() WHERE patient_id = %s",
                (ids["C3"],),
            )
        after = {r["pseudonym"] for r in research_rows(client, env)}
        assert pseudonym(key, ids["C3"]) not in after and pseudonym(key, ids["C1"]) in after
        env.export()  # 4 consenting patients are left in the cell -> k < 5 -> cell suppressed
        assert not (
            {r["pseudonym"] for r in research_rows(client, env)}
            & {pseudonym(key, ids[k]) for k in ("C1", "C2")}
        )
    finally:
        with env.owner_conn() as c, c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            c.execute(
                "UPDATE clinic.consents SET research_ok = true WHERE patient_id = %s", (ids["C3"],)
            )
        env.export()


def test_non_researchers_cannot_read_research(client, env):
    from m5_backend.app.auth import issue_token

    for k in ("A1", "N1", "P1", "Ph1"):
        tok = issue_token(env.settings, env.directory.by_key(k))
        assert (
            client.get(
                "/research/encounters", headers={"Authorization": f"Bearer {tok}"}
            ).status_code
            == 403
        )


def test_researcher_cannot_write_research_or_read_clinic(env):
    from m5_backend.app.auth import Principal

    u = env.directory.by_key("R1")
    for stmt in ["DELETE FROM research.encounters_deid", "SELECT 1 FROM clinic.patients LIMIT 1"]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with env.api_db.request_tx(Principal(u.id, u.role, u.facility_id), commit=False) as cur:
                cur.execute(stmt)
