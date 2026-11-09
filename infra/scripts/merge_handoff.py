"""Merge one module's handoff notes into the shared root documents.

Why: several builder agents run in parallel. If they all edited
docs/DECISIONS_EXPLAINED.md at once they would overwrite each other. Instead each
builder writes ONLY inside its own folder:

    <module>/handoff/decisions.md        -> docs/DECISIONS_EXPLAINED.md (renumbered D-<n>, index rows)
    <module>/handoff/glossary.md         -> docs/glossary.md (terms already present are skipped)
    <module>/handoff/ai_usage.md         -> docs/ai_usage.md (appended)
    <module>/handoff/human_todo.md       -> HUMAN_TODO.md (appended)
    <module>/handoff/open_questions.md   -> docs/open_questions.md (appended)
    <module>/handoff/licences.md         -> docs/licences.md (new table rows only)

and the orchestrator (one writer at a time) runs:

    uv run python infra/scripts/merge_handoff.py m1_data [--dry-run]

Processed parts are moved to <module>/handoff/merged/<UTC timestamp>/ so a second
run does nothing. A part that is empty or only HTML comments is skipped and left
in place. All target files are computed first and written only if every step
succeeds (no half-merged state).

Formats builders must use:
  decisions.md : entries with headings '### D-?: <title>   (<Phase> / <module> / <agent> / <date>)'
                 (any D-number is replaced by the next free number), bullets as in the
                 section 11 template, including '- What we chose:' and '- Status:'.
  glossary.md  : '- **Term**: definition' (indented continuation lines allowed).
  licences.md  : markdown table rows '| item | type | licence | URL fetched | allowed |'.
"""

from __future__ import annotations

import argparse
import itertools
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PARTS = {
    "decisions.md": "docs/DECISIONS_EXPLAINED.md",
    "glossary.md": "docs/glossary.md",
    "ai_usage.md": "docs/ai_usage.md",
    "human_todo.md": "HUMAN_TODO.md",
    "open_questions.md": "docs/open_questions.md",
    "licences.md": "docs/licences.md",
}
INDEX_END = "<!-- INDEX-END -->"
ENTRIES_END = "<!-- ENTRIES-END -->"
GLOSSARY_END = "<!-- GLOSSARY-END -->"
LICENCES_END = "<!-- LICENCES-END -->"

HEADING = re.compile(r"^### D-[^:\n]*:[ \t]*(?P<rest>.*)$", re.MULTILINE)
EXISTING_ID = re.compile(r"^### D-(\d+):", re.MULTILINE)
TERM = re.compile(r"^- \*\*(?P<term>.+?)\*\*")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
SEPARATOR_ROW = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$")


def _meaningful(text: str) -> bool:
    return bool(COMMENT.sub("", text).strip())


def _insert_before(doc: str, marker: str, block: str, target: str) -> str:
    if marker not in doc:
        raise ValueError(f"{target}: marker {marker} not found; cannot merge safely")
    # Use the LAST occurrence: entries may quote the marker text (D-8 does), and the
    # real marker always sits after all entries.
    i = doc.rindex(marker)
    return doc[:i] + block + doc[i:]


def _cell(s: str, limit: int = 120) -> str:
    s = " ".join(s.split())
    if len(s) > limit:
        s = s[: limit - 3].rstrip() + "..."
    return s.replace("|", "\\|")


def _split_entries(text: str) -> list[str]:
    starts = [m.start() for m in HEADING.finditer(text)]
    if not starts:
        return []
    starts.append(len(text))
    return [text[a:b].rstrip() + "\n" for a, b in itertools.pairwise(starts)]


def _bullet(entry: str, label: str) -> str:
    m = re.search(rf"^- {re.escape(label)}:[ \t]*(.*)$", entry, re.MULTILINE)
    return m.group(1).strip() if m and m.group(1).strip() else "unknown"


def merge_decisions(target_doc: str, part: str, module: str) -> tuple[str, list[str]]:
    entries = _split_entries(part)
    if not entries:
        raise ValueError(f"{module}/handoff/decisions.md has no '### D-?:' headings")
    used = [int(n) for n in EXISTING_ID.findall(target_doc)]
    nxt = max(used, default=0) + 1
    new_entries, rows, ids = [], [], []
    for entry in entries:
        m = HEADING.match(entry)
        rest = m.group("rest").strip()
        meta = re.search(r"\(([^()]*)\)\s*$", rest)
        title = rest[: meta.start()].strip() if meta else rest
        meta_parts = [p.strip() for p in meta.group(1).split("/")] if meta else []
        where = " / ".join(meta_parts[:2]) if len(meta_parts) >= 2 else module
        new_id = f"D-{nxt}"
        nxt += 1
        ids.append(new_id)
        new_entries.append(HEADING.sub(f"### {new_id}: {rest}", entry, count=1))
        rows.append(
            f"| {new_id} | {_cell(where)} | {_cell(title)} | "
            f"{_cell(_bullet(entry, 'Status'), 40)} | {_cell(_bullet(entry, 'What we chose'))} |\n"
        )
    doc = _insert_before(target_doc, INDEX_END, "".join(rows), "DECISIONS_EXPLAINED.md")
    doc = _insert_before(doc, ENTRIES_END, "\n".join(new_entries) + "\n", "DECISIONS_EXPLAINED.md")
    return doc, ids


def merge_glossary(target_doc: str, part: str) -> tuple[str, list[str]]:
    known = {m.group("term").strip().lower() for m in map(TERM.match, target_doc.splitlines()) if m}
    blocks: list[list[str]] = []
    for line in part.splitlines():
        if TERM.match(line):
            blocks.append([line])
        elif blocks and line.strip():
            blocks[-1].append(line)
    added, out = [], []
    for b in blocks:
        term = TERM.match(b[0]).group("term").strip()
        if term.lower() in known:
            continue
        known.add(term.lower())
        added.append(term)
        out.append("\n".join(b) + "\n")
    if not out:
        return target_doc, []
    if GLOSSARY_END in target_doc:
        return _insert_before(target_doc, GLOSSARY_END, "".join(out), "glossary.md"), added
    return target_doc.rstrip("\n") + "\n" + "".join(out), added


def merge_licences(target_doc: str, part: str) -> tuple[str, int]:
    existing = {" ".join(line.split()) for line in target_doc.splitlines()}
    header_seen = any(line.startswith("|") for line in target_doc.splitlines())
    rows = []
    for line in part.splitlines():
        line = line.rstrip()
        if not line.startswith("|") or SEPARATOR_ROW.match(line):
            continue
        norm = " ".join(line.split())
        if norm in existing:
            continue
        if header_seen and norm.lower().startswith("| item |"):
            continue
        existing.add(norm)
        rows.append(line + "\n")
    if not rows:
        return target_doc, 0
    if LICENCES_END in target_doc:
        return _insert_before(target_doc, LICENCES_END, "".join(rows), "licences.md"), len(rows)
    return target_doc.rstrip("\n") + "\n" + "".join(rows), len(rows)


def merge_append(target_doc: str, part: str, module: str, timestamp: str) -> str:
    return (
        target_doc.rstrip("\n")
        + f"\n\n## From {module} (merged {timestamp})\n\n"
        + (part.strip() + "\n")
    )


def merge(
    root: Path | str, module: str, *, timestamp: str | None = None, dry_run: bool = False
) -> str:
    """Merge <root>/<module>/handoff/* into the root docs. Returns a short report."""
    root = Path(root)
    handoff = root / module / "handoff"
    if not handoff.is_dir():
        raise FileNotFoundError(f"{handoff} does not exist")
    timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pending: dict[Path, str] = {}  # target path -> new content
    processed: list[Path] = []
    report: list[str] = []

    def current(rel: str) -> str:
        p = root / rel
        if p in pending:
            return pending[p]
        if not p.exists():
            raise FileNotFoundError(f"target {rel} does not exist")
        return p.read_text(encoding="utf-8")

    for name, rel in PARTS.items():
        src = handoff / name
        if not src.exists():
            continue
        part = src.read_text(encoding="utf-8")
        if not _meaningful(part):
            report.append(f"skip {name}: empty or comments only")
            continue
        part = COMMENT.sub("", part)
        doc = current(rel)
        if name == "decisions.md":
            doc, ids = merge_decisions(doc, part, module)
            report.append(f"decisions: added {', '.join(ids)}")
        elif name == "glossary.md":
            doc, terms = merge_glossary(doc, part)
            report.append(f"glossary: added {len(terms)} term(s) {terms}")
        elif name == "licences.md":
            doc, n = merge_licences(doc, part)
            report.append(f"licences: added {n} row(s)")
        else:
            doc = merge_append(doc, part, module, timestamp)
            report.append(f"{name}: appended to {rel}")
        pending[root / rel] = doc
        processed.append(src)

    if not processed:
        report.append("nothing to merge")
    if dry_run:
        return "DRY RUN\n" + "\n".join(report)
    for path, content in pending.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    if processed:
        dest = handoff / "merged" / timestamp
        dest.mkdir(parents=True, exist_ok=False)
        for src in processed:
            shutil.move(str(src), str(dest / src.name))
        report.append(f"moved {len(processed)} part(s) to {dest.relative_to(root).as_posix()}")
    return "\n".join(report)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge <module>/handoff/* into root docs.")
    ap.add_argument("module", help="module folder, e.g. m1_data")
    ap.add_argument("--root", default=Path(__file__).resolve().parents[2], type=Path)
    ap.add_argument("--timestamp", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        print(merge(args.root, args.module, timestamp=args.timestamp, dry_run=args.dry_run))
    except (ValueError, FileNotFoundError) as exc:
        print(f"merge_handoff: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
