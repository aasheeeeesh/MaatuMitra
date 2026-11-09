# Infrastructure inventory

Constraint 1: $0 budget, local-first. Every free tier or cloud tool ever used must be
listed here (m2_asr appends compute runs; m7_eval appends the final summary and writes
infra/cost_report.md).

## 1. Dev machine (hardware part, architect, probed 2026-11-09)

All values below were read on this machine on 2026-11-09 with the command shown.

| item | value | how it was read |
|---|---|---|
| OS | Windows 11 Home Single Language 10.0.26200 | `Get-CimInstance Win32_OperatingSystem` |
| CPU | 12th Gen Intel Core i7-12650H, 16 logical CPUs | `Win32_Processor`, `nproc` |
| RAM | 15.6 GB | `Win32_ComputerSystem.TotalPhysicalMemory` |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4096 MiB VRAM, driver 566.07, CUDA (driver) 12.7 | `nvidia-smi` |
| Free disk | ~11-12 GB free on C: (246 GB total, 96% used) **HARD CONSTRAINT** | `df -h /c` |
| Python (project) | CPython 3.11.15, uv-managed | `uv venv --python <managed 3.11.15 path>` |
| uv | 0.12.1 | `uv --version` |
| make | GNU Make 4.4.1 as `mingw32-make` (C:\mingw64\bin); no `make` on PATH | `mingw32-make --version` |
| bash | Git Bash (`/usr/bin/bash`), needed by the Makefile | `which bash` |
| git | 2.55.0.windows.3 | `git --version` |
| Docker | **not available** (no `docker` CLI on PATH) | `which docker` |
| PostgreSQL | **not installed** (`psql` not on PATH). MariaDB 12.0 is installed but is NOT Postgres | `which psql`, PATH |
| ffmpeg | N-124279-g0f6ba39122-20260430 | `ffmpeg -version` |
| Ollama | installed; models `qwen3:4b-instruct` (2.5 GB), `nomic-embed-text:latest` (274 MB) | `ollama list` |
| gitleaks | not installed locally (runs in CI and via pre-commit) | `which gitleaks` |
| Windows long paths | `LongPathsEnabled = 0` (registry, read only) | `Get-ItemProperty HKLM:\...\FileSystem` |

### Consequences

- **Disk**: heavy ML packages (torch, faster-whisper, transformers, TTS) are OPTIONAL
  extras in pyproject.toml (`asr`, `tts`, `llm`, `helper`); `make setup` installs only the
  light base set (~400 MB venv). Model weights must not be stored in the repo; download
  only what a run needs and delete what is not needed; log sizes here.
- **GPU 4 GB**: Whisper large-v3 in fp16 probably does not fit; int8 small/medium are the
  realistic local choices (UNVERIFIED until m2 runs them). Larger runs go to a free
  Colab/Kaggle GPU via HUMAN_TODO.
- **Long paths**: the repo lives under a ~180-character path. A `.venv` inside the repo
  hit Windows MAX_PATH (a jsonschema file could not be opened). The Makefile therefore
  puts the env at `%USERPROFILE%/.venvs/maatumitra` on Windows
  (`UV_PROJECT_ENVIRONMENT`). We did not change the system long-path setting (that is
  a system setting change).
- **uv-managed Python quirk**: `uv python install 3.11` and `uv venv --python 3.11` failed
  with "Missing expected target directory for Python minor version link" (uv 0.12.1 on
  this machine). Workaround used: point `uv venv` at the managed interpreter path directly.
  CI on Linux is not affected (UNVERIFIED until CI runs).

## 2. Network reachability (2026-11-09, `curl -w %{http_code}`)

| host | result |
|---|---|
| https://huggingface.co | 200 |
| https://pypi.org/simple/ | 200 |
| https://github.com | 200 |
| https://commonvoice.mozilla.org/ | 200 |
| https://datasets-server.huggingface.co/ | 404 on `/` (host reachable; root path has no page) |
| https://registry-1.docker.io/v2/ | 401 (reachable; auth needed, normal for the registry API) |
| https://hub.docker.com tags API | reachable; returned the postgres:16.15 digest |

## 3. PostgreSQL plan (no Docker)

Decision D-4 in docs/DECISIONS_EXPLAINED.md. Summary:
- Keep `docker-compose.yml` (postgres:16.15 pinned by digest, port `127.0.0.1:5432:5432`)
  for people who have Docker. Never run on this laptop.
- On this laptop m5_backend obtains Postgres 16 WITHOUT Docker. Candidates, both to be
  VERIFIED by m5_backend before use:
  1. `pgserver` on PyPI: exists (PyPI JSON API read 2026-11-09: version 0.1.4, summary
     "Self-contained postgres server for your python applications"). Which Postgres
     major version it bundles, its licence and Windows support: UNVERIFIED.
  2. EnterpriseDB portable binaries zip for PostgreSQL 16 on Windows: not fetched yet,
     UNVERIFIED (URL, licence, size).
  (`postgresql-wheel` on PyPI exists too, version 14.1.2 = PostgreSQL 14, so it does not
  meet the Postgres 16 default.)
- Whatever is used must bind to 127.0.0.1 only and keep its data dir git-ignored.

## 4. Free tiers / cloud used

None yet (2026-11-09). Cloud spend so far: $0.

## 5. Compute log

(m2_asr and others append rows: date, what, where (local GPU / CPU / Colab / Kaggle),
hours, model + revision, outcome.)
