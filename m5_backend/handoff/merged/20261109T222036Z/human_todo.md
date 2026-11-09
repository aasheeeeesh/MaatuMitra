- [ ] **Add the m5 database job to CI** (UNVERIFIED until it runs on GitHub; the architect owns `.github/workflows/ci.yml`). Add this job:
  ```yaml
    m5-db:
      runs-on: ubuntu-24.04
      services:
        postgres:
          image: postgres:16.15@sha256:f9a7b9ebf6f56201f949db745e47bc423c0f0f8294bafe991cc10bf74b029657  # same pin as docker-compose.yml
          env:
            POSTGRES_USER: mm_bootstrap
            POSTGRES_PASSWORD: ci-bootstrap-throwaway
            POSTGRES_DB: postgres
          ports:
            - 127.0.0.1:54329:5432
          options: >-
            --health-cmd "pg_isready -U mm_bootstrap -d postgres"
            --health-interval 5s --health-timeout 5s --health-retries 20
      env:
        POSTGRES_HOST: 127.0.0.1
        POSTGRES_PORT: "54329"
        PG_BOOTSTRAP_USER: mm_bootstrap
        PG_BOOTSTRAP_PASSWORD: ci-bootstrap-throwaway
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
        - name: Throw-away secrets for this run only
          run: |
            for k in POSTGRES_PASSWORD API_DB_PASSWORD JWT_SIGNING_KEY RESEARCH_PSEUDONYM_HMAC_KEY MOCK_LOGIN_PASSWORD; do
              echo "$k=$(openssl rand -hex 32)" >> "$GITHUB_ENV"
            done
        - run: uv python install && make setup
        - name: m5 DB tests incl. the E5 access matrix against real PostgreSQL 16
          run: uv run pytest m5_backend/tests -m needs_db -rs
  ```
  After the first run check: no `needs_db ... SKIPPED` lines, 60 DB tests passed, and the log line `unauthorized successes: 0 of 1385 ...`. If GitHub rejects the `127.0.0.1:` prefix in `ports`, use `54329:5432` (the runner is a throw-away VM). Optionally upload `results/m5_backend/` as an artifact (pin the action to a SHA).
- [ ] Review the hand-written expected table `m5_backend/tests/access_matrix_expected.yaml` against your own reading of PROJECT_BRIEF AGENT 6 (the same AI wrote the table and the SQL).
- [ ] UNVERIFIED: authenticity of the EnterpriseDB zip (no vendor checksum found; sha256 `43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281`). Optional: check the digital signature of `%USERPROFILE%\.maatumitra\pg16\pgsql\bin\postgres.exe` (right-click > Properties > Digital Signatures).
- [ ] UNVERIFIED: EDB third-party licence notices (`pgsql/commandlinetools_3rd_party_licenses.txt` in the zip) were not reviewed.
- [ ] Decide (clinical/product): may nurses read approved/saved records? Who records research consent (today only the operator via maint_role)?
- [ ] Docker users: set `POSTGRES_USER`/`POSTGRES_PASSWORD` in `.env` equal to `PG_BOOTSTRAP_USER`/`PG_BOOTSTRAP_PASSWORD` (NOT `owner_role`), or owner_role would be the image's superuser (`dbtool` refuses to continue then).
- [ ] Local DB: start `bash m5_backend/scripts/db_up.sh` (resets the `maatumitra` DB; `--no-reset` only starts), stop `bash m5_backend/scripts/db_down.sh`. Data: `%USERPROFILE%\.maatumitra\pgdata16` (outside the repo).
