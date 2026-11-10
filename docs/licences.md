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
| indic-transliteration 2.3.82 | tool (Python package, extra `data`) | MIT (PyPI page) | https://pypi.org/project/indic-transliteration/ (2026-11-09) | yes |
| AI4Bharat IndicXlit (considered, not used) | model/tool | MIT (README: "code (and models) are released under the MIT License") | https://github.com/AI4Bharat/IndicXlit (2026-11-09) | yes (not used) |
| India NLEM 2022 PDF (strengths, listing) | government document | UNVERIFIED (no licence statement read) | https://nppa.gov.in/storage/uploads/pdf/nlem-2022pdf-0cd1d2b28855bf30128875ab19fc5304.pdf (2026-11-09) | UNVERIFIED (facts only cited) |
| WHO AWaRe antibiotic portal list (AWaRe classes) | dataset/web page | UNVERIFIED | https://aware.essentialmeds.org/list (2026-11-09) | UNVERIFIED (facts only cited) |
| openFDA drug labels (dose ranges) | dataset | public domain US Government data per the firecrawl openFDA provider attribution; FDA policy page not fetched (UNVERIFIED) | https://api.fda.gov/drug/label.json (22 label records, 2026-11-09) | UNVERIFIED (likely yes) |
| ISMP List of Confused Drug Names | document | UNVERIFIED (ECRI/ISMP copyright) | https://online.ecri.org/hubfs/ISMP/Resources/ISMP_ConfusedDrugNames.pdf (2026-11-09) | UNVERIFIED (only drug-pair names cited) |
| Wikipedia "Kannada grammar", "Kannada script"; kn.wikipedia "ಜ್ವರ"; Wiktionary Kannada cardinal numbers | reference text | CC BY-SA (site licence; UNVERIFIED per page) | https://en.wikipedia.org/wiki/Kannada_grammar ; https://en.wikipedia.org/wiki/Kannada_script ; https://kn.wikipedia.org/wiki/ಜ್ವರ ; https://en.wiktionary.org/wiki/Category:Kannada_cardinal_numbers (2026-11-09) | yes with attribution (UNVERIFIED) |
| News18 Kannada antibiotic article | news text | all rights reserved (assumed); only single words/short phrases used | https://kannada.news18.com/news/national-international/kidney-damage-due-to-excessive-use-of-antibiotics-and-other-tablets-ach-ws-l-2494291.html (2026-11-09) | UNVERIFIED (words only) |
| CARE Hospitals Kannada ORS page | web text | all rights reserved (assumed); only single words used | https://www.carehospitals.com/kn/blog-detail/how-to-prepare-oral-rehydration-solution-and-its-benifits/ (2026-11-09) | UNVERIFIED (words only) |
| m1 generated synthetic text data (data/gold, transcripts, twins) | dataset (ours) | NOASSERTION until the repo licence is chosen | n/a | yes (own synthetic data) |
| Noto Sans Kannada v2.006 (slim variable TTF `NotoSansKannada[wght].ttf`, bundled as m6_ui/static/fonts/NotoSansKannada-VF.ttf, sha256 b062c3ec551cee95b88cbbc470036c81b69c788516fd8910ba6ae6e3c70d9bb2; release zip sha256 902b1b92018f7c96862d68d0a39ef03b978203cd4c3f55d6760f597657b51c44) | font | SIL Open Font License 1.1 (OFL-1.1; text copied to m6_ui/static/fonts/OFL.txt) | https://github.com/notofonts/kannada/releases/download/NotoSansKannada-v2.006/NotoSansKannada-v2.006.zip and https://raw.githubusercontent.com/notofonts/kannada/main/OFL.txt (fetched 2026-11-10) | yes (bundling with software allowed; keep OFL.txt next to the font) |
| Qwen3 4B Instruct (Ollama tag qwen3:4b-instruct, digest 0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0, Q4_K_M) | model weights (local, via Ollama) | Apache-2.0 (as printed by `ollama show qwen3:4b-instruct` on 2026-11-10; upstream model card not fetched: UNVERIFIED) | none fetched (licence text read from the local Ollama manifest) | yes (local inference only, weights not redistributed) |
| en.wiktionary.org Kannada entries (ಒಂದು ... ಹತ್ತು, ಹದಿನಾಲ್ಕು, ಅರ್ಧ, ಸಲ, ದಿನ, ದಿವಸ, ವಾರ, ತಿಂಗಳು, ಚಮಚ, ಜ್ವರ, ಕೆಮ್ಮು, ಚಳಿ, ನೋವು) | dictionary facts used to check word lists (no text copied) | CC BY-SA 4.0 (Wiktionary site licence; not re-checked per page) | https://en.wiktionary.org/w/index.php?title=<word>&action=raw (fetched 2026-11-10) | yes (single words, cited) |
| NHS paracetamol adult dosing page | web page (dose range source) | UNVERIFIED (NHS website terms) | https://www.nhs.uk/medicines/paracetamol-for-adults/how-and-when-to-take-paracetamol-for-adults/ (fetched by clinical reviewer 2026-11-10) | UNVERIFIED |
| NHS metformin page | web page (usage source) | UNVERIFIED | https://www.nhs.uk/medicines/metformin/how-and-when-to-take-metformin/ | UNVERIFIED |
| WHO diarrhoeal disease fact sheet | web page (ORS usage) | UNVERIFIED | https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease | UNVERIFIED |
<!-- LICENCES-END -->
