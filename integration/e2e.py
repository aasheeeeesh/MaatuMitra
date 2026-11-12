"""End to end on DEV conversations through the REAL m5 HTTP API.

gold text -> mock ASR transcript -> m3 rules record -> (m4 via the adapter inside the API) ->
asha creates household/patient/encounter/record -> physician verifies, resolves flags as a
reviewer would, saves -> every role reads the record back (RLS) -> m6's own HttpGate loads it.

CLI:  uv run python -m integration.e2e   (DB must be up; writes results/integration/e2e_dev.md)
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

from integration import pipeline
from integration.apiserver import USERS_FILE, api, db_up, env_value

REPO = pipeline.REPO
OUT = REPO / "results" / "integration"
PORT = 8000

# Who reads the record back and what RLS should answer (m5 sql/020_rls.sql policies).
# Before save: asha (own household), nurse (facility, draft/flagged), physician (facility) yes;
# other asha, other facility, pharmacist, researcher no.
# After save: the nurse policy only shows draft/flagged, so the nurse loses access.
READERS = ["A1", "N1", "N2", "P1", "P2", "A2", "A3", "N3", "P3", "Ph1", "R1"]
EXPECT_BEFORE = {"A1", "N1", "N2", "P1", "P2"}
EXPECT_AFTER = {"A1", "P1", "P2"}
# the encounter author must hold the matching role (asha creates only household visits)
AUTHOR = {"asha_household_visit": "A1", "nurse_consult": "N1", "physician_consult": "P1"}


class Client:
    def __init__(self, base: str):
        pw = env_value("MOCK_LOGIN_PASSWORD")
        assert pw, "MOCK_LOGIN_PASSWORD not set in .env"
        self.pw = pw
        users = json.loads(USERS_FILE.read_text("utf-8"))["users"]
        self.users = {u["key"]: u["id"] for u in users}
        self.http = httpx.Client(base_url=base, timeout=20)
        self.tok: dict[str, str] = {}

    def h(self, who: str) -> dict[str, str]:
        if who not in self.tok:
            r = self.http.post(
                "/auth/token", json={"username": self.users[who], "password": self.pw}
            )
            assert r.status_code == 200, (who, r.status_code)
            self.tok[who] = r.json()["access_token"]
        return {"Authorization": f"Bearer {self.tok[who]}"}

    def call(self, who: str, method: str, path: str, body: Any = None) -> httpx.Response:
        return self.http.request(method, path, headers=self.h(who), json=body)


def flags(verdict: dict) -> list[tuple[str, str]]:
    return sorted(
        {(c["check_id"], c["field_path"]) for c in verdict["checks"] if c["status"] == "flag"}
    )


def setup(c: Client, tag: str, n: int, record: dict, transcript: dict, tdir: Path):
    """A1 creates household + patient; the role matching the encounter type creates the encounter
    and draft record. Returns ids."""
    hh = c.call("A1", "POST", "/households", {})
    assert hh.status_code == 201, hh.text
    body = {
        "household_id": hh.json()["id"],
        "name_synthetic": f"SYNTHETIC-{tag}-{n}",
        "age_band": "25-34",
        "sex": "F",
    }
    pt = c.call("A1", "POST", "/patients", body)
    assert pt.status_code == 201, pt.text
    enc = {"patient_id": pt.json()["id"], "encounter_type": record["encounter_type"]}
    author = AUTHOR.get(record["encounter_type"], "P1")
    en = c.call(author, "POST", "/encounters", enc)
    assert en.status_code == 201, en.text
    eid = en.json()["id"]
    (tdir / f"{eid}.json").write_text(json.dumps(transcript, ensure_ascii=False), encoding="utf-8")
    rc = c.call(author, "POST", "/records", {"encounter_id": eid, "record": record})
    assert rc.status_code == 201, rc.text
    return eid, rc.json()["id"]


def read_back(c: Client, rid: str) -> dict[str, int]:
    return {k: c.call(k, "GET", f"/records/{rid}").status_code for k in READERS}


def unflip(planted: dict, path: str) -> dict:
    """The reviewer's edit: flip the planted boolean back (the transcript says so)."""
    rec = copy.deepcopy(planted)
    cur: Any = rec
    parts = path.strip("/").split("/")
    for p in parts[:-1]:
        cur = cur[int(p)] if p.isdigit() else cur[p]
    cur[parts[-1]] = not cur[parts[-1]]
    return rec


def run_one(
    c: Client,
    tag: str,
    n: int,
    cid: str,
    record: dict,
    transcript: dict,
    tdir: Path,
    planted_path: str | None = None,
    m6_base: str | None = None,
) -> dict[str, Any]:
    """One conversation. For a planted record the reviewer EDITS the flagged field back."""
    row: dict[str, Any] = {"id": cid, "kind": "planted" if planted_path else "natural"}
    eid, rid = setup(c, tag, n, record, transcript, tdir)
    row["before"] = read_back(c, rid)
    if m6_base:  # the live review screen loads the DRAFT first; its verify is then NOT the newest
        row["m6"] = m6_view(m6_base, c, {"record_id": rid})  # (m5 refuses a stale verdict id)
    v = c.call("A1", "POST", f"/records/{rid}/verify", {})  # asha may verify
    assert v.status_code == 201, v.text
    row["asha_flags"] = len(v.json()["unresolved"])
    v = c.call("P1", "POST", f"/records/{rid}/verify", {})
    assert v.status_code == 201, v.text
    vj = v.json()
    fl = flags(vj["verdict"])
    row["flags"] = [f"{a}{p}" for a, p in fl]
    row["verifier_version"] = vj["verdict"]["verifier_version"]
    row["auto"] = vj["verdict"]["auto_acceptable"]
    row["reasons"] = sorted(
        {
            f"{x['check_id']} {x['reason'].split(' ')[0].rstrip(':')}"
            for x in vj["verdict"]["checks"]
            if x["status"] == "flag"
        }
    )
    save_url = f"/records/{rid}/save"
    s0 = c.call("P1", "POST", save_url, {"verdict_id": vj["verdict_id"], "resolutions": []})
    row["save_without_resolution"] = s0.status_code  # 409 if a flag is open, 200 if none
    action = "confirmed"
    if planted_path:
        action = "edited"
        pu = c.call("P1", "PATCH", f"/records/{rid}", {"record": unflip(record, planted_path)})
        assert pu.status_code == 200, pu.text
        v2 = c.call("P1", "POST", f"/records/{rid}/verify", {})
        assert v2.status_code == 201, v2.text
        row["flags_after_edit"] = len(v2.json()["unresolved"])
    if row["save_without_resolution"] == 200:  # nothing was open: already saved
        res: list[dict] = []
        sv = s0
    else:
        res = [{"check_id": a, "field_path": p, "action": action} for a, p in fl]
        sv = c.call("P1", "POST", save_url, {"verdict_id": vj["verdict_id"], "resolutions": res})
    row["resolutions"] = [f"{r['action']}:{r['check_id']}{r['field_path']}" for r in res]
    row["save_status"] = sv.status_code
    got = c.call("P1", "GET", f"/records/{rid}").json()
    row["final_status"] = got["status"]
    row["approved_by_physician"] = got["approved_by"] == c.users["P1"]
    row["after"] = read_back(c, rid)
    t = c.call("P1", "GET", f"/records/{rid}/transcript")
    row["transcript_ok"] = t.status_code == 200 and t.json()["text"] == transcript["text"]
    row["record_id"], row["encounter_id"] = rid, eid
    row["roundtrip_json_equal"] = got["json"] == (
        unflip(record, planted_path) if planted_path else record
    )
    row["verify_after_save"] = c.call("P1", "POST", f"/records/{rid}/verify", {}).status_code
    if m6_base:  # after save: can the same screen reload it? (verify only accepts unsaved records)
        row["m6_reload_after_save"] = m6_view(m6_base, c, row)["loaded"]
    return row


def m6_view(base: str, c: Client, row: dict) -> dict[str, Any]:
    """m6's own HttpGate (what the live review screen uses) loads the record from m5; m6's
    Catalogue builds the case with the transcript served by m5."""
    from m6_ui import gate
    from m6_ui.data import Catalogue

    if not hasattr(c, "gate"):  # one login only: the API rate-limits logins (5 per minute)
        c.gate = gate.HttpGate(base)
        c.gate_login = c.gate.login(c.users["P1"], c.pw).ok
    g = c.gate
    out: dict[str, Any] = {"login": c.gate_login}
    ld = g.load_record(row["record_id"])
    out["loaded"] = ld.ok
    if ld.ok:
        cat = Catalogue(REPO)
        tr = c.call("P1", "GET", f"/records/{row['record_id']}/transcript").json()
        cat._transcripts[tr["audio_id"]] = tr
        case = cat.case_for(ld.data["record"], ld.data["verdict"])
        out["case_errors"] = list(case.errors)
    return out


def run_all(n: int = 10, port: int = PORT) -> dict[str, Any]:
    ok, why = db_up()
    if not ok:
        raise RuntimeError(f"needs_db: {why}")
    ids = pipeline.select_ids(n)
    work = Path(tempfile.mkdtemp(prefix="mm_integration_"))
    asr_dir, m5_dir = OUT / "asr_mock", work / "m5_transcripts"
    m5_dir.mkdir()
    trs, recs = {}, {}
    for cid in ids:
        trs[cid] = pipeline.mock_asr(cid)
        pipeline.write_json(trs[cid], asr_dir / f"{cid}.json")
        recs[cid] = pipeline.extract_record(cid, trs[cid])
    rows, planted_rows, m6 = [], [], []
    with api(port, [asr_dir], m5_dir, work / "api.log") as base:
        c = Client(base)
        for i, cid in enumerate(ids):
            rows.append(
                run_one(
                    c, "E2E", i, cid, recs[cid], trs[cid], m5_dir, None, base if i < 3 else None
                )
            )
        # planted-error records are reported separately (never pooled with natural ones)
        clean = [r["id"] for r in rows if not r["flags"]][:2] or ids[:2]
        for j, cid in enumerate(clean):
            bad, path = pipeline.plant_negation_flip(recs[cid])
            bad = {**bad, "record_id": f"planted-{cid}"}
            planted_rows.append(run_one(c, "PLANT", j, cid, bad, trs[cid], m5_dir, path))
        m6 = [{"id": r["id"], **r["m6"], "reload_after_save": r["m6_reload_after_save"]}
              for r in rows[:3]]  # fmt: skip
    return {"ids": ids, "rows": rows, "planted": planted_rows, "m6": m6}


def _rls(d: dict, expect: set[str]) -> str:
    bad = [k for k, v in d.items() if (v == 200) != (k in expect)]
    return "as expected" if not bad else "UNEXPECTED: " + ",".join(f"{k}={d[k]}" for k in bad)


def _table(rows: list[dict]) -> list[str]:
    head = (
        "| # | id | flags | save w/o resolution | resolutions | save | final | "
        "RLS before save | RLS after save | transcript |"
    )
    out = [head, "|" + "---|" * 10]
    for i, r in enumerate(rows, 1):
        out.append(
            f"| {i} | {r['id']} | {', '.join(r['flags']) or 'none'} | {r['save_without_resolution']}"
            f" | {', '.join(r['resolutions']) or '-'} | {r['save_status']} | {r['final_status']}"
            f" | {_rls(r['before'], EXPECT_BEFORE)} | {_rls(r['after'], EXPECT_AFTER)}"
            f" | {'ok' if r['transcript_ok'] else 'FAIL'} |"
        )
    return out


def render_md(res: dict[str, Any]) -> str:
    n_ok = sum(r["save_status"] == 200 and r["final_status"] == "saved" for r in res["rows"])
    lines = [
        "# E2E on DEV conversations (integration-qa, Phase C1)",
        "",
        f"Seeded choice (seed {pipeline.SEED}) of {len(res['ids'])} ids from data/splits/dev.txt; "
        "the test split is never touched.",
        "Path: gold text -> mock ASR transcript (m2 build_transcript; m2 has no real dev output "
        "for these template ids) -> m3 rules record.v1 -> real m5 HTTP API on 127.0.0.1 with "
        "MAATUMITRA_VERIFIER=integration.verifier_adapter:verify_record (m4) -> physician P1 "
        "resolves flags -> save -> read back as 11 users -> m6 HttpGate + Catalogue load it.",
        "",
        f"Natural conversations processed: {len(res['rows'])}/{len(res['ids'])}; saved: {n_ok}.",
        "",
        "## Natural records (m3 output as-is)",
        "",
        *_table(res["rows"]),
        "",
        "Reviewer rule used: every open flag is `confirmed`. This is a test policy, not clinical "
        "advice. 'save w/o resolution' = a save with an empty resolution list (409 = refused "
        "because a flag is open; 200 = nothing was open).",
        "",
        "## Planted-error records (separate table, never pooled with natural ones)",
        "",
        *_table(res["planted"]),
        "",
        "For planted records the reviewer first tries to save without a resolution (409), edits "
        "the flipped field back, re-verifies (flags_after_edit below) and saves with `edited`.",
        "",
    ]
    for r in res["planted"]:
        lines.append(f"- {r['id']}: flags_after_edit = {r.get('flags_after_edit')}")
    lines += ["", "## Flag reasons on natural records (check + m4 reason code)", ""]
    lines += [f"- {r['id']}: {', '.join(r['reasons']) or 'none'}" for r in res["rows"]]
    lines += [
        "",
        "## m6 view (HttpGate.load_record + Catalogue.case_for), first 3 records, DRAFT before save",
        "",
    ]
    lines += [f"- {m['id']}: {m}" for m in res["m6"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    res = run_all()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e2e_dev.md").write_text(render_md(res), encoding="utf-8")
    (OUT / "e2e_dev.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    print("wrote", OUT / "e2e_dev.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
