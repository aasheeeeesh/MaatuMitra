"""E4 planted-mistake generator (deterministic, seeded).

Types (PROJECT_BRIEF AGENT 5 step 4):
  a negation drop   b negation add   c digit change   d digit-order swap   e unit change
  f drug swap (confusable from the lexicon)   g frequency swap   h duration swap   i wrong patient_ref

RECORD level (tests the verifier): the gold-derived record is mutated; the transcript stays the
gold transcript. TRANSCRIPT level (simulates an ASR error): the transcript TEXT is mutated and the
record is rebuilt the way a faithful extractor would read the corrupted text, so record and
transcript agree with each other. Text-only checks can then only catch it indirectly (range,
omission, ambiguity); the second-transcript condition of C7 shows what an ASR cross-check adds.
Type i has no transcript-level version (a patient link is not spoken audio).

Source gold: a directory of gold.v1 JSON files or a gold.v1 JSONL file. DEV ONLY: any path with a
"test" component is refused (refuse_test_split). Duplicated mutations are NOT independent trials;
each injection carries `unique_key` so reports can show unique counts next to N.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

import regex

from m4_verify.lexicon import Lexicon, parse_durations, parse_frequencies
from m4_verify.negation import analyze, span_polarity
from m4_verify.numbers import parse_numbers
from m4_verify.textnorm import KN_DIGITS, tokens

TYPES = {
    "a": "negation drop",
    "b": "negation add",
    "c": "digit change",
    "d": "digit-order swap",
    "e": "unit change",
    "f": "drug swap (confusable)",
    "g": "frequency swap",
    "h": "duration swap",
    "i": "wrong patient_ref",
}
SEED = 20261109
TOKEN_RE = regex.compile(r"[\p{L}\p{M}\p{N}]+")
UNITS = ["mg", "g", "mcg", "ml", "tablet", "capsule"]
FREQS = [1, 2, 3, 4, 6]
DURS = [1, 2, 3, 5, 7, 10, 14]
KN_NUM_WORDS = {
    1: "ಒಂದು",
    2: "ಎರಡು",
    3: "ಮೂರು",
    4: "ನಾಲ್ಕು",
    5: "ಐದು",
    6: "ಆರು",
    7: "ಏಳು",
    10: "ಹತ್ತು",
    14: "ಹದಿನಾಲ್ಕು",
}
ASCII_TO_KN = {v: k for k, v in KN_DIGITS.items()}
TEST_COMPONENT = regex.compile(r"(^|[_.\-])test([_.\-]|$)", regex.IGNORECASE)


# --------------------------------------------------------------------------- inputs
def refuse_test_split(path: str | Path) -> None:
    """Raise if the path looks like TEST-split data (PROJECT_BRIEF 6.5: tune/evaluate on DEV only)."""
    p = Path(path).resolve()
    root = Path(__file__).resolve().parents[1]
    try:
        parts = p.relative_to(root).parts
    except ValueError:
        parts = p.parts
    for part in parts:
        if TEST_COMPONENT.search(part):
            raise ValueError(f"refusing to read '{path}': looks like TEST-split data (DEV only)")


def load_gold_dir(path: str | Path, ids: set[str] | None = None) -> list[dict[str, Any]]:
    refuse_test_split(path)
    p = Path(path)
    docs: list[dict[str, Any]] = []
    if p.is_dir():
        for f in sorted(p.glob("*.json")):
            docs.append(json.loads(f.read_text(encoding="utf-8")))
        for f in sorted(p.glob("*.jsonl")):
            refuse_test_split(f)
            docs += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        docs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    docs = [d for d in docs if d.get("schema_version") == "gold.v1"]
    if ids is not None:
        docs = [d for d in docs if d["conversation_id"] in ids]
    return sorted(docs, key=lambda d: d["conversation_id"])


def _words(text: str) -> list[dict[str, Any]]:
    return [
        {
            "w": m.group(),
            "char_start": m.start(),
            "char_end": m.end(),
            "start": None,
            "end": None,
            "conf": None,
        }
        for m in TOKEN_RE.finditer(text)
    ]


def make_transcript(audio_id: str, text: str, source: str = "template_text") -> dict[str, Any]:
    return {
        "schema_version": "transcript.v1",
        "audio_id": audio_id,
        "source": source,
        "model": {"name": "gold", "revision": "m4_verify-planted"},
        "text": text,
        "words": _words(text),
        "latency_ms": None,
        "audio_duration_s": None,
        "hardware": None,
        "created_at": "2026-11-09T12:00:00Z",
    }


def gold_to_pair(gold: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Gold conversation -> (gold transcript.v1, record.v1 with evidence = gold spans)."""
    cid = gold["conversation_id"]
    text = "\n".join(t["text"] for t in gold["turns"])
    tr = make_transcript(cid, text)
    gr = gold["gold_record"]

    def ev(gs):
        return {
            "span_text": gs["span_text"],
            "char_start": gs["char_start"],
            "char_end": gs["char_end"],
            "audio_start": None,
            "audio_end": None,
        }

    def strip(item):
        d = {k: v for k, v in item.items() if k != "gold_span"}
        d["evidence"] = ev(item["gold_span"])
        return d

    rec = {
        "schema_version": "record.v1",
        "record_id": f"rec-{cid}",
        "patient_ref": gr["patient_ref"],
        "encounter_type": gr["encounter_type"],
        "source_transcript_id": cid,
        "extractor": {"name": "gold", "version": "gold.v1"},
        "status": "draft",
        "symptoms": [strip(x) for x in gr["symptoms"]],
        "medications": [strip(x) for x in gr["medications"]],
        "advice": [strip(x) for x in gr["advice"]],
        "follow_up": strip(gr["follow_up"]) if gr.get("follow_up") else None,
    }
    return tr, rec


# --------------------------------------------------------------------------- json pointer helpers
def _get(doc: dict, path: str) -> Any:
    cur: Any = doc
    for part in path.strip("/").split("/"):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def _set(doc: dict, path: str, value: Any) -> None:
    parts = path.strip("/").split("/")
    cur: Any = doc
    for part in parts[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


def _items(rec: dict) -> list[tuple[str, str, dict]]:
    out = []
    for kind in ("symptoms", "medications", "advice"):
        for i, it in enumerate(rec[kind]):
            out.append((f"/{kind}/{i}", kind, it))
    return out


def _num(v: float) -> float | int:
    return int(v) if float(v).is_integer() else v


# --------------------------------------------------------------------------- value mutations
def _digit_change(v: float, rng: random.Random, lim: float) -> float | None:
    s = str(_num(v))
    pos = [i for i, ch in enumerate(s) if ch.isdigit()]
    for _ in range(20):
        i = rng.choice(pos)
        d = rng.choice([x for x in "0123456789" if x != s[i]])
        new = s[:i] + d + s[i + 1 :]
        try:
            val = _num(float(new))
        except ValueError:
            continue
        if 0 < val <= lim and val != v:
            return val
    return None


def _digit_swap(v: float, rng: random.Random, lim: float) -> float | None:
    s = str(_num(v))
    pairs = [
        i for i in range(len(s) - 1) if s[i].isdigit() and s[i + 1].isdigit() and s[i] != s[i + 1]
    ]
    if not pairs:
        return None
    i = rng.choice(pairs)
    new = s[:i] + s[i + 1] + s[i] + s[i + 2 :]
    val = _num(float(new))
    return val if 0 < val <= lim and val != v else None


LIMITS = {"dose_value": 1e7, "frequency_per_day": 24, "duration_days": 365}


def _record_candidates(t: str, rec: dict) -> list[str]:
    c = []
    for path, kind, it in _items(rec):
        if t in "ab":
            neg = (not it["present"]) if kind == "symptoms" else it["negated"]
            fld = "present" if kind == "symptoms" else "negated"
            if (t == "a" and neg) or (t == "b" and not neg):
                c.append(f"{path}/{fld}")
        elif kind == "medications":
            if t in "cd":
                for f in ("dose_value", "frequency_per_day", "duration_days"):
                    probe = random.Random(0)  # noqa: S311 (only checks that a swap exists)
                    if it[f] is not None and (
                        t == "c" or _digit_swap(it[f], probe, LIMITS[f]) is not None
                    ):
                        c.append(f"{path}/{f}")
            elif t == "e" and it["dose_unit"] is not None:
                c.append(f"{path}/dose_unit")
            elif t == "f":
                c.append(f"{path}/drug")
            elif t == "g" and it["frequency_per_day"] is not None:
                c.append(f"{path}/frequency_per_day")
            elif t == "h" and it["duration_days"] is not None:
                c.append(f"{path}/duration_days")
    if t == "i":
        c.append("/patient_ref")
    return c


def _swap_drug(
    drug: str, lex: Lexicon, rng: random.Random, need_in_lexicon: bool
) -> tuple[str, str] | None:
    conf = (
        [d for d in lex.drugs.get(drug, None).confusable if d != drug] if drug in lex.drugs else []
    )
    if need_in_lexicon:
        conf = [d for d in conf if d in lex.drugs]
    if conf:
        return rng.choice(conf), "confusable_with from the lexicon"
    others = sorted(d for d in lex.drugs if d != drug)
    if not others:
        return None
    return rng.choice(others), "FALLBACK: no confusable listed; another lexicon drug"


def _mutate_value(
    t: str, path: str, before: Any, rec: dict, lex: Lexicon, rng: random.Random, patients: list[str]
):
    fld = path.rsplit("/", 1)[1]
    if t in "ab":
        return (not before), ""
    if t == "c":
        return _digit_change(before, rng, LIMITS[fld]), ""
    if t == "d":
        return _digit_swap(before, rng, LIMITS[fld]), ""
    if t == "e":
        return rng.choice([u for u in UNITS if u != before]), ""
    if t == "f":
        r = _swap_drug(before, lex, rng, need_in_lexicon=False)
        return (r[0], r[1]) if r else (None, "")
    if t == "g":
        return rng.choice([f for f in FREQS if f != before]), ""
    if t == "h":
        return rng.choice([d for d in DURS if d != before]), ""
    if t == "i":
        others = [p for p in patients if p != before] or [f"pt-planted-{rng.randrange(10**6):06d}"]
        return rng.choice(others), ""
    raise ValueError(t)


def generate_record_level(
    golds: list[dict], lex: Lexicon, n_per_type: int = 200, seed: int = SEED
) -> list[dict]:
    pairs = [gold_to_pair(g) for g in golds]
    patients = sorted({rec["patient_ref"] for _, rec in pairs})
    out: list[dict] = []
    for t in TYPES:
        rng = random.Random(f"{seed}-record-{t}")  # noqa: S311 (deterministic seeded sampling, not crypto)
        cands = [(k, p) for k, (_, rec) in enumerate(pairs) for p in _record_candidates(t, rec)]
        if not cands:
            continue
        made = attempts = 0
        while made < n_per_type and attempts < n_per_type * 50:
            k, path = cands[attempts % len(cands)]
            attempts += 1
            tr, rec = pairs[k]
            before = _get(rec, path)
            after, note = _mutate_value(t, path, before, rec, lex, rng, patients)
            if after is None or after == before:
                continue
            new = copy.deepcopy(rec)
            _set(new, path, after)
            made += 1
            out.append(
                {
                    "id": f"E4-R-{t}-{made:04d}",
                    "type": t,
                    "type_name": TYPES[t],
                    "level": "record",
                    "source_id": golds[k]["conversation_id"],
                    "field_path": path,
                    "before": before,
                    "after": after,
                    "note": note,
                    "unique_key": f"{golds[k]['conversation_id']}|{path}|{after}",
                    "record": new,
                    "transcript": tr,
                    "clean_transcript": tr,
                    "true_patient_ref": rec["patient_ref"],
                }
            )
    return out


# --------------------------------------------------------------------------- transcript-level edits
def _apply_edit(text: str, a: int, b: int, rep: str) -> str:
    return text[:a] + rep + text[b:]


def _shift_evidence(rec: dict, new_text: str, a: int, b: int, rep: str) -> None:
    delta = len(rep) - (b - a)
    for _, _, it in _items(rec) + (
        [("/follow_up", "follow_up", rec["follow_up"])] if rec.get("follow_up") else []
    ):
        ev = it["evidence"]
        cs, ce = ev["char_start"], ev["char_end"]
        if b <= cs:
            cs, ce = cs + delta, ce + delta
        elif a >= ce:
            pass
        else:
            cs = min(cs, a) if a < cs else cs
            ce = max(cs + 1, ce + delta)
        span = new_text[cs:ce]
        while span and span[0].isspace():
            cs += 1
            span = span[1:]
        while span and span[-1].isspace():
            ce -= 1
            span = span[:-1]
        ev.update(char_start=cs, char_end=ce, span_text=span)


AFFIRM = [
    ("S-UDILLA", "ುದಿಲ್ಲ", "ುತ್ತೇನೆ"),
    ("S-ILLA", "ಿಲ್ಲ", "ಿದೆ"),
    ("S-DIDDARE", "ದಿದ್ದರೆ", "ಿದ್ದರೆ"),
    ("S-DIDRE", "ದಿದ್ರೆ", "ಿದ್ರೆ"),
    ("S-BAARADU", "ಬಾರದು", "ಬೇಕು"),
    ("S-KOODADU", "ಕೂಡದು", "ಬಹುದು"),
    ("S-BEDI", "ಬೇಡಿ", "ಿ"),
    ("S-BEDA", "ಬೇಡ", "ು"),
    ("V-DE", "ದೆ", "ಿ"),
    ("V-LLA", "ಲ್ಲ", "ುತ್ತೆ"),
    ("SOFT-LLA", "ಲ್ಲ", "ುತ್ತೆ"),
    ("S-VALLA", "ವಲ್ಲ", "ವು"),
    ("S-DIRU", "ದಿರುವುದು", "ಿರುವುದು"),
]
DELETE_RULES = {"W-ILLA", "W-ILLAA", "C-YAAVUDE", "W-ALLA", "EN-NOT", "SOFT-ILLADA"}
REPLACE_WHOLE = {
    "W-BEDA": "ಬೇಕು",
    "W-BEDI": "ಬೇಕು",
    "W-BAARADU": "ಬೇಕು",
    "W-KOODADU": "ಬಹುದು",
    "W-NEGQ": "ಇದೆಯಾ",
}


def _negation_drop_edit(text: str, cs: int, ce: int) -> tuple[int, int, str, str] | None:
    an = analyze(text)
    pol = span_polarity(an, cs, ce)
    if pol.cross_turn == "negative":
        # the bare answer token in the next turn
        for c in an.clauses:
            if (
                c.idx > max(pol.clause_ids)
                and len(c.toks) == 1
                and c.toks[0].text in ("ಇಲ್ಲ", "ಇಲ್ಲಾ")
            ):
                tk = c.toks[0]
                return tk.start, tk.end, "ಹೌದು", "bare answer ಇಲ್ಲ -> ಹೌದು"
        return None
    if not pol.cues:
        return None
    cue = pol.cues[0]
    tok = text[cue.start : cue.end]
    if cue.rule_id in DELETE_RULES:
        a = cue.start
        while a > 0 and text[a - 1] == " ":
            a -= 1
        return a, cue.end, "", f"deleted '{tok}'"
    if cue.rule_id in REPLACE_WHOLE:
        return (
            cue.start,
            cue.end,
            REPLACE_WHOLE[cue.rule_id],
            f"'{tok}' -> '{REPLACE_WHOLE[cue.rule_id]}'",
        )
    for rid, suf, rep in AFFIRM:
        if cue.rule_id == rid and tok.endswith(suf):
            new = tok[: -len(suf)] + rep
            return cue.start, cue.end, new, f"'{tok}' -> '{new}'"
    return None


def _negation_add_edit(text: str, cs: int, ce: int) -> tuple[int, int, str, str] | None:
    an = analyze(text)
    pol = span_polarity(an, cs, ce)
    if not pol.clause_ids:
        return None
    cl = an.clauses[pol.clause_ids[-1]]
    for t in cl.toks:
        if t.text == "ಇದೆ":
            return t.start, t.end, "ಇಲ್ಲ", "'ಇದೆ' -> 'ಇಲ್ಲ'"
    return cl.end, cl.end, " ಬೇಡ", "inserted ' ಬೇಡ' at clause end"


def _surface_digits(text: str, a: int, b: int, value: float) -> str:
    s = str(_num(value))
    if any(ch in KN_DIGITS for ch in text[a:b]):
        s = "".join(ASCII_TO_KN.get(ch, ch) for ch in s)
    return s


def _transcript_candidates(t: str, rec: dict) -> list[str]:
    if t == "i":
        return []
    return _record_candidates(t, rec)


def _transcript_edit(t: str, path: str, tr: dict, rec: dict, lex: Lexicon, rng: random.Random):
    """Return (edit tuple (a, b, rep, note), new record value) or None if not applicable."""
    text = tr["text"]
    item_path = "/".join(path.split("/")[:3])
    item = _get(rec, item_path)
    cs, ce = item["evidence"]["char_start"], item["evidence"]["char_end"]
    span = text[cs:ce]
    fld = path.rsplit("/", 1)[1]
    before = _get(rec, path)
    if t == "a":
        e = _negation_drop_edit(text, cs, ce)
        return (e, not before) if e else None
    if t == "b":
        e = _negation_add_edit(text, cs, ce)
        return (e, not before) if e else None
    if t in "cd":
        nums = [n for n in parse_numbers(span) if n.is_digit and float(n.value) == float(before)]
        if fld != "dose_value" or not nums:
            return None  # only spoken digits can suffer a digit-level ASR error
        n = nums[0]
        after = (
            _digit_change(before, rng, LIMITS[fld])
            if t == "c"
            else _digit_swap(before, rng, LIMITS[fld])
        )
        if after is None:
            return None
        rep = _surface_digits(text, cs + n.start, cs + n.end, after)
        return (
            cs + n.start,
            cs + n.end,
            rep,
            f"'{text[cs + n.start : cs + n.end]}' -> '{rep}'",
        ), after
    if t == "e":
        toks = tokens(span)
        from m4_verify.lexicon import parse_dose_phrases

        dp = [
            d for d in parse_dose_phrases(span) if float(d.value) == float(item["dose_value"] or -1)
        ]
        if not dp:
            return None
        d = dp[0]
        unit_toks = [tk for tk in toks if d.start <= tk.start and tk.end <= d.end][1:]
        if not unit_toks:
            return None
        a, b = cs + unit_toks[0].start, cs + unit_toks[-1].end
        after = rng.choice([u for u in ("g", "mcg", "ml", "tablet") if u != before])
        rep = {"tablet": "ಮಾತ್ರೆ"}.get(after, after)
        return (a, b, rep, f"'{text[a:b]}' -> '{rep}'"), after
    if t == "f":
        mentions = [(d, a, b) for d, a, b in lex.drugs_in(span) if d == before]
        r = _swap_drug(before, lex, rng, need_in_lexicon=True)
        if not mentions or not r:
            return None
        _, a, b = mentions[0]
        after = r[0]
        orig = span[a:b]
        rep = lex.drugs[after].kn_primary if any("ಀ" <= ch <= "೿" for ch in orig) else after
        return (cs + a, cs + b, rep, f"'{orig}' -> '{rep}' ({r[1]})"), after
    if t in "gh":
        qs = parse_frequencies(span) if t == "g" else parse_durations(span)
        qs = [q for q in qs if float(q.value) == float(before)]
        if not qs:
            return None
        q = qs[0]
        nums = [n for n in parse_numbers(span) if n.start == q.start]
        if not nums:
            return None
        n = nums[0]
        mult = 7 if (t == "h" and q.unit == "week") else 1
        choices = [v for v in KN_NUM_WORDS if v * mult != before and v <= (6 if t == "g" else 14)]
        v = rng.choice(choices)
        rep = KN_NUM_WORDS[v] if not n.is_digit else str(v)
        return (cs + n.start, cs + n.end, rep, f"'{span[n.start : n.end]}' -> '{rep}'"), v * mult
    return None


def generate_transcript_level(
    golds: list[dict], lex: Lexicon, n_per_type: int = 200, seed: int = SEED
) -> list[dict]:
    pairs = [gold_to_pair(g) for g in golds]
    out: list[dict] = []
    for t in TYPES:
        if t == "i":
            continue
        rng = random.Random(f"{seed}-transcript-{t}")  # noqa: S311 (deterministic seeded sampling, not crypto)
        cands = [(k, p) for k, (_, rec) in enumerate(pairs) for p in _transcript_candidates(t, rec)]
        if not cands:
            continue
        made = attempts = 0
        while made < n_per_type and attempts < n_per_type * 50:
            k, path = cands[attempts % len(cands)]
            attempts += 1
            tr, rec = pairs[k]
            res = _transcript_edit(t, path, tr, rec, lex, rng)
            if res is None:
                continue
            (a, b, rep, note), after = res
            new_text = _apply_edit(tr["text"], a, b, rep)
            new_rec = copy.deepcopy(rec)
            _set(new_rec, path, after)
            _shift_evidence(new_rec, new_text, a, b, rep)
            new_tr = make_transcript(tr["audio_id"], new_text)
            made += 1
            out.append(
                {
                    "id": f"E4-T-{t}-{made:04d}",
                    "type": t,
                    "type_name": TYPES[t],
                    "level": "transcript",
                    "source_id": golds[k]["conversation_id"],
                    "field_path": path,
                    "before": _get(rec, path),
                    "after": after,
                    "note": f"transcript edit at [{a},{b}): {note}",
                    "unique_key": f"{golds[k]['conversation_id']}|{path}|{a}|{b}|{rep}",
                    "record": new_rec,
                    "transcript": new_tr,
                    "clean_transcript": tr,
                    "true_patient_ref": rec["patient_ref"],
                }
            )
    return out


LOG_KEYS = (
    "id",
    "type",
    "type_name",
    "level",
    "source_id",
    "field_path",
    "before",
    "after",
    "note",
    "unique_key",
)


def log_rows(injections: list[dict]) -> list[dict]:
    return [{k: inj[k] for k in LOG_KEYS} for inj in injections]
