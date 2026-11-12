"""`make m6-mock`: headless MOCK MODE run on fixtures (no browser, no other module).

Writes:
- results/m6_ui/mock_summary.json : per fixture record, rows / flags / flagged-first check,
  approve state with no answers, and the mock gate's answer after confirming every flag;
- results/m6_ui/conjunct_test_page.html : standalone Kannada rendering test page that loads
  the bundled font by relative path (open it in a browser, or screenshot it headless).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "m6_ui"


def main() -> int:
    if os.environ.get("MODE", "mock") != "mock":
        print("m6 mock_run: set MODE=mock", file=sys.stderr)
        return 2
    from m6_ui import data, gate, highlight, i18n, review

    cat = data.Catalogue(ROOT)
    out = []
    ok = True
    for rid in cat.record_ids():
        case = cat.case(rid)
        rows = review.build_rows(case.record, case.verdict)
        flags = [r.path for r in rows if r.flags]
        first_ok = [bool(r.flags) for r in rows] == sorted(
            (bool(r.flags) for r in rows), reverse=True
        )
        resolved: dict = {}
        before = review.approve_enabled(case.verdict, resolved)
        for r in rows:
            if r.flags:
                review.mark_row(resolved, r, "confirmed")
        g = gate.MockGate()
        if case.verdict:
            vid = g.store_verdict(rid, case.record, case.verdict)
            answers = review.build_resolutions(review.flags_from_verdict(case.verdict), resolved)
            res = g.save(rid, vid, answers or [], "physician")
        else:
            res = gate.GateResult(False, 0, "refused_stale")
        markup = (
            highlight.render_transcript(
                case.transcript["text"], highlight.spans_for_record(case.record, case.verdict)
            )
            if case.transcript
            else ""
        )
        inert = "<script" not in markup and "<img" not in markup
        ok &= first_ok and inert and (not flags or not before)
        out.append(
            {
                "record_id": rid,
                "load_errors": case.errors,
                "rows": len(rows),
                "flagged_rows": flags,
                "flagged_first": first_ok,
                "approve_enabled_before_answers": before,
                "gate_after_confirming_all": res.code,
                "transcript_markup_inert": inert,
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mock_summary.json").write_text(
        json.dumps(
            {"mode": "mock", "all_checks_ok": ok, "records": out}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    items = json.loads((ROOT / "m6_ui" / "conjuncts.json").read_text(encoding="utf-8"))["items"]
    rows_html = "".join(
        f'<div class="c"><p class="k">{highlight.esc(it["text"])}</p><p class="m">'
        f"{' '.join(f'U+{ord(ch):04X}' for ch in it['text'])} | {highlight.esc(it['what'])}</p></div>"
        for it in items
    )
    title = f"{i18n.t('font.title', 'kn')} / {i18n.t('font.title', 'en')}"
    page = (
        '<!doctype html><html lang="kn"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{highlight.esc(title)}</title><style>"
        '@font-face{font-family:"Noto Sans Kannada";src:url("../../m6_ui/static/fonts/NotoSansKannada-VF.ttf") format("truetype");font-weight:100 900}'
        'body{font-family:"Noto Sans Kannada",sans-serif;font-size:18px;line-height:1.6;margin:16px;max-width:760px;background:#FBF8F3;color:#1C1B1A}'
        ".k{font-size:40px;margin:0}.m{font-family:Consolas,monospace;font-size:18px;color:#4A4743;margin:0 0 8px 0}"
        ".c{border-bottom:1px solid #8A847C}</style></head><body>"
        f"<h1>{highlight.esc(title)}</h1><p>{highlight.esc(i18n.t('font.intro', 'kn'))}</p>"
        f"<p>{highlight.esc(i18n.t('font.intro', 'en'))}</p>{rows_html}</body></html>"
    )
    (OUT / "conjunct_test_page.html").write_text(page, encoding="utf-8")
    print(f"m6 mock_run: {len(out)} records, all_checks_ok={ok}; wrote {OUT / 'mock_summary.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
