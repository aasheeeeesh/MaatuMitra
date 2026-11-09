# Third-party licences

One row per dataset, model, font or tool. "URL fetched" must be a page actually fetched
in a session; otherwise UNVERIFIED. Builders add rows through `<module>/handoff/licences.md`.
The licence of THIS repository is not chosen yet (LICENSE_PLACEHOLDER.md).

| Item | Type | Licence | URL fetched | Allowed for coursework |
|---|---|---|---|---|
| uv | tool | UNVERIFIED (believed MIT OR Apache-2.0) | UNVERIFIED | UNVERIFIED |
| Python packages in uv.lock | libraries | various; not yet listed one by one | UNVERIFIED | UNVERIFIED |
| frontend-design plugin skill (not used; own skill written) | skill | Apache-2.0 (LICENSE.txt in the local plugin folder, read 2026-11-09) | local file, not a URL | n/a (not used) |
| postgres:16.15 Docker image | database | UNVERIFIED (PostgreSQL Licence expected) | UNVERIFIED | UNVERIFIED |
| pgserver 0.1.4 (candidate only) | database package | PyPI JSON gave no licence field | https://pypi.org/pypi/pgserver/json | UNVERIFIED |
| PostgreSQL 16.15 server binaries (EnterpriseDB Windows x86-64 zip; only bin/lib/share used) | tool | PostgreSQL License (read in the zip's `pgsql/server_license.txt`, 2026-11-09) | https://www.postgresql.org/about/licence/ (fetched 2026-11-09); https://www.enterprisedb.com/download-postgresql-binaries (fetched 2026-11-09) | yes (permissive). EDB third-party notices (`commandlinetools_3rd_party_licenses.txt`) not reviewed: UNVERIFIED |
| pgserver 0.1.4 (evaluated, NOT used) | tool | Apache-2.0 (LICENSE file on GitHub) | https://raw.githubusercontent.com/orm011/pgserver/main/LICENSE (fetched 2026-11-09) | not used (ships PostgreSQL 16.2; see decision) |
| Kannada Wikipedia article "ಜ್ವರ" (52 sentences in m4_verify/audit/) | text | CC BY-SA 4.0 (Wikipedia text licence; attribution in the file header) | https://kn.wikipedia.org/wiki/ಜ್ವರ (fetched 2026-11-10) | yes, with attribution and share-alike (UNVERIFIED by a human) |
| Vijay Karnataka health article (only single words tested, no text stored) | news text | copyright, all rights reserved (not checked in detail) | https://vijaykarnataka.com/lifestyle/health/why-its-important-to-not-neglect-fever-in-the-summer/articleshow/120721236.cms (fetched 2026-11-10) | read-only use for a test; no text redistributed |
<!-- LICENCES-END -->
