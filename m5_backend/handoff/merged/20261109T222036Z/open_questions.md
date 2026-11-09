## m5_backend (2026-11-10)

1. UNVERIFIED: the E5 matrix has run only locally (PostgreSQL 16.15, Windows 11). The CI job (snippet in m5_backend/handoff/human_todo.md) has not run yet.
2. UNVERIFIED: authenticity of the EnterpriseDB PostgreSQL 16.15 zip (no vendor checksum found) and its third-party licence notices.
3. Request to the architect: `.env.example` has `POSTGRES_USER=owner_role`. With Docker, `POSTGRES_USER` becomes the image's SUPERUSER, which would make owner_role a superuser. Please change the placeholder to `POSTGRES_USER=mm_bootstrap` (m5 may only add keys). dbtool refuses to run if owner_role is a superuser.
4. Clinical scope: nurses cannot read approved/saved records ("draft records" read as draft|flagged). Intended?
5. Consent workflow: no app role can create or change consents (default deny). Who records consent in the product?
6. The saved gate trusts the verdict.v1 the client sends; it does not re-run m4_verify, and verdict.v1 has no way to mark a flag "resolved by a human". Should m5 store verdicts server-side / should a contract bump add resolution?
7. Residual (by design, documented): raw `api_login` / `owner_role` / bootstrap credentials can set GUCs, SET ROLE, or disable triggers; they must stay in `.env` on the API host only.
8. The rule-of-three bound 3/1385 assumes independent trials; the cases share policies, so it is optimistic.
