"""Deterministic generator: templates + lexicon -> gold.v1, gold transcript.v1, twins,
splits, manifest, test lock.

    uv run python -m m1_data generate            # writes data/ (refuses to change test.lock)
    uv run python data/generate.py               # same, thin wrapper

Determinism: every conversation has its own RNG seeded with sha256(SEED, template, index);
timestamps are a fixed constant; files are written with "\\n" line endings.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path

from m1_data import kn
from m1_data.config import CONSENT_NOTE, CREATED_AT, ROOT, SEED, VERSION
from m1_data.lexicon import LEXICON_CSV, load_lexicon
from m1_data.negation import NON_CUE_IDS, load_table, trap_tokens_in
from m1_data.render import (
    PLACEHOLDER,
    SYMPTOMS,
    CountFill,
    DrugFill,
    NegFill,
    SymptomFill,
    WordFill,
    render_text,
)
from m1_data.split import lock_text, plan_combos, plan_families, seed_int, sha256_bytes
from m1_data.templates import TEMPLATES_DIR, load_templates


class EmptyPool(Exception):
    pass


class GenerationError(Exception):
    pass


# ---------------------------------------------------------------- slot filling


def _drug_candidates(spec, lex, chosen, combo_split, split):
    where = spec.get("where", {})
    out = []
    for g in sorted(lex):
        d = lex[g]
        if "class" in where and d.cls not in where["class"]:
            continue
        if "generic" in where and g not in where["generic"]:
            continue
        if "form" in where:
            if d.form not in where["form"]:
                continue
        elif d.form in spec.get("exclude_form", ["injection"]):
            continue
        needs = spec.get("needs", [])
        if ("freq" in needs and not d.freqs) or ("dur" in needs and not d.durs):
            continue
        if g in chosen:
            continue
        combos = []
        if spec.get("dose", "none") == "given":
            combos = [c for c in d.dosed_combos() if combo_split.get(c) == split]
            if not combos:
                continue
        out.append((d, combos))
    return out


def fill_slots(t, i: int, rng: random.Random, lex, combo_split, split) -> dict:
    fills: dict = {}
    for sid, spec in t.slots.items():
        typ = spec["type"]
        excl = [fills[x] for x in spec.get("distinct_from", [])]
        if typ == "drug":
            chosen = {f.drug.generic for f in excl}
            cands = _drug_candidates(spec, lex, chosen, combo_split, split)
            if not cands:
                raise EmptyPool(f"{t.id}:{sid} has no candidate drug in split {split}")
            d, combos = rng.choice(cands)
            dose = None
            if combos:
                c = rng.choice(combos)
                dose = (c[1], c[2])
            needs = spec.get("needs", [])
            freq = rng.choice(d.freqs) if "freq" in needs else None
            dur = rng.choice(d.durs) if "dur" in needs else None
            fills[sid] = DrugFill(drug=d, dose=dose, freq=freq, dur=dur, rng=rng)
        elif typ == "symptom":
            taken = {f.name for f in excl}
            pool = [s for s in spec["pool"] if s not in taken]
            name = rng.choice(pool)
            fills[sid] = SymptomFill(name=name, kn=SYMPTOMS[name])
        elif typ == "count":
            fills[sid] = CountFill(n=rng.choice(spec["values"]))
        elif typ == "word":
            fills[sid] = WordFill(text=rng.choice(spec["choices"]))
        elif typ in ("neg", "xturn"):
            forms = spec["forms"]
            form = forms[i % len(forms)]
            if spec.get("link"):
                negative = fills[spec["link"]].negative
            else:
                negative = rng.random() < spec.get("p_neg", 1.0)
            fills[sid] = NegFill(
                neg=form["neg"],
                pos=form["pos"],
                patterns=list(form["patterns"]),
                negative=negative,
                cross_turn=(typ == "xturn"),
            )
    return fills


# ---------------------------------------------------------------- one conversation


def _sub_text(text: str, fills: dict) -> str:
    return PLACEHOLDER.sub(lambda m: fills[m.group(1)].attr(m.group(2)), text)


def _slot_turn(t, sid: str) -> int:
    hits = [k for k, turn in enumerate(t.turns) if "{" + sid + "}" in turn["text"]]
    if len(hits) != 1:
        raise GenerationError(f"{t.id}: slot {sid} must appear in exactly one turn, got {hits}")
    return hits[0]


def build_conversation(t, i: int, fills: dict, split: str, table) -> tuple[dict, dict, list[dict]]:
    cid = f"m1-{t.id}-{i:03d}"
    texts, local = [], {}
    for k, turn in enumerate(t.turns):
        txt, spans = render_text(turn["text"], fills)
        texts.append(txt)
        for mid, se in spans.items():
            local[mid] = (k, *se)
    offsets = [sum(len(x) + 1 for x in texts[:k]) for k in range(len(texts))]
    conv_text = "\n".join(texts)

    def span(mid: str) -> dict:
        k, s, e = local[mid]
        return {
            "turn_index": k,
            "span_text": texts[k][s:e],
            "char_start": offsets[k] + s,
            "char_end": offsets[k] + e,
        }

    gr = {
        "patient_ref": f"pt-m1-{t.id}-{i:03d}",
        "encounter_type": t.encounter,
        "symptoms": [],
        "medications": [],
        "advice": [],
        "follow_up": None,
    }
    for it in t.items:
        negative = fills[it["neg"]].negative if "neg" in it else bool(it.get("negated", False))
        sp = span(it["span"])
        kind = it["kind"]
        if kind == "symptom":
            name = fills[it["slot"]].name if "slot" in it else it["name"]
            gr["symptoms"].append({"name": name, "present": not negative, "gold_span": sp})
        elif kind == "medication":
            f = fills[it["slot"]]
            fields = it.get("fields", [])
            dv, du = f.dose if (f.dose and "dose" in fields) else (None, None)
            gr["medications"].append(
                {
                    "drug": f.drug.generic,
                    "dose_value": dv,
                    "dose_unit": du,
                    "frequency_per_day": f.freq if "freq" in fields else None,
                    "duration_days": f.dur if "dur" in fields else None,
                    "negated": negative,
                    "gold_span": sp,
                }
            )
        else:
            text = it["text"] if (negative or "neg" not in it) else it["text_pos"]
            text = _sub_text(text, fills)
            if kind == "advice":
                gr["advice"].append({"text": text, "negated": negative, "gold_span": sp})
            else:
                gr["follow_up"] = {"text": text, "gold_span": sp}
    for g in ("symptoms", "medications", "advice"):
        gr[g].sort(key=lambda x: x["gold_span"]["char_start"])

    # ---- negation self-check against the shared table
    detected = table.detect_conversation(texts)
    expected = set()
    for f in fills.values():
        if isinstance(f, NegFill) and f.negative:
            expected |= set(f.patterns)
    if (detected - NON_CUE_IDS) != (expected - NON_CUE_IDS):
        raise GenerationError(
            f"{cid}: negation cues detected {sorted(detected - NON_CUE_IDS)} != declared "
            f"{sorted(expected - NON_CUE_IDS)} in {texts}"
        )

    gold = {
        "schema_version": "gold.v1",
        "conversation_id": cid,
        "template_family_id": t.family,
        "turns": [
            {"speaker_role": turn["role"], "text": txt}
            for turn, txt in zip(t.turns, texts, strict=True)
        ],
        "gold_record": gr,
        "tags": {
            "has_negation": bool(detected - NON_CUE_IDS),
            "trap_tokens": trap_tokens_in(conv_text),
            "code_switched": kn.has_latin(conv_text),
            "cross_turn_negation": "NEG-X01" in detected,
        },
    }
    transcript = {
        "schema_version": "transcript.v1",
        "audio_id": cid,
        "source": "template_text",
        "model": {"name": "gold", "revision": VERSION},
        "text": conv_text,
        "words": [
            {"w": w, "char_start": s, "char_end": e, "start": None, "end": None, "conf": None}
            for w, s, e in kn.tokens(conv_text)
        ],
        "latency_ms": None,
        "audio_duration_s": None,
        "hardware": None,
        "created_at": CREATED_AT,
    }

    # ---- minimal-pair twins: one per negative neg/xturn slot
    twins = []
    for sid, f in fills.items():
        if not (isinstance(f, NegFill) and f.negative):
            continue
        k = _slot_turn(t, sid)
        ttext, tspans = render_text(t.turns[k]["text"], fills, flip={sid})
        items = []
        for it in t.items:
            if it.get("neg") != sid:
                continue
            mk, s, e = local[it["span"]]
            if mk == k:
                where, ts, te, base_t = "turn", *tspans[it["span"]], ttext
            else:
                where, ts, te, base_t = "previous_turn", s, e, texts[mk]
            items.append(
                {
                    "kind": it["kind"],
                    "label": (
                        fills[it["slot"]].drug.generic
                        if it["kind"] == "medication"
                        else fills[it["slot"]].name
                        if "slot" in it
                        else it.get("name", it.get("text"))
                    ),
                    "negated_original": True,
                    "negated_twin": False,
                    "span_in": where,
                    "negated_span": [s, e],
                    "negated_span_text": texts[mk][s:e],
                    "twin_span": [ts, te],
                    "twin_span_text": base_t[ts:te],
                }
            )
        twins.append(
            {
                "twin_id": f"{cid}__{sid}",
                "conversation_id": cid,
                "template_id": t.id,
                "template_family_id": t.family,
                "split": split,
                "turn_index": k,
                "slot": sid,
                "primary_pattern": f.patterns[0],
                "patterns": f.patterns,
                "cross_turn": f.cross_turn,
                "previous_turn_text": texts[k - 1] if k > 0 else None,
                "negated_text": texts[k],
                "twin_text": ttext,
                "cue_text": f.neg,
                "positive_text": f.pos,
                "items": items,
                "generator_version": VERSION,
                "native_validated": False,
            }
        )
    return gold, transcript, twins


# ---------------------------------------------------------------- whole dataset


def _retry(fn, tries: int = 20) -> None:
    """Windows: another process (indexer, antivirus) may hold a file for a moment."""
    for k in range(tries):
        try:
            fn()
            return
        except PermissionError:
            if k == tries - 1:
                raise
            time.sleep(0.25)


def _dump(doc) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _jsonl(rows) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n" for r in rows).encode(
        "utf-8"
    )


def _manifest_row(path: str, content: bytes, split: str, parent: str | None) -> dict:
    return {
        "schema_version": "manifest.v1",
        "file": path,
        "sha256": sha256_bytes(content),
        "bytes": len(content),
        "source": "template_text",
        "split": split,
        "noise_snr_db": None,
        "speed_factor": None,
        "voice_or_speaker": "none",
        "dialect": "unknown",
        "licence_spdx": "NOASSERTION",
        "licence_url": "UNVERIFIED",
        "retrieved_at": CREATED_AT,
        "generator_version": VERSION,
        "seed": SEED,
        "parent_id": parent,
        "consent_note": CONSENT_NOTE,
        "native_validated": False,
    }


def generate(
    out_root: Path = ROOT,
    lexicon_path: Path = LEXICON_CSV,
    templates_dir: Path = TEMPLATES_DIR,
    per_template: int | None = None,
    mock: bool = False,
    refreeze: bool = False,
) -> dict:
    out_root = Path(out_root)
    lex = load_lexicon(lexicon_path)
    templates = sorted(load_templates(templates_dir), key=lambda t: t.id)
    table = load_table()
    fam_split = plan_families(templates)
    combo_split = plan_combos(lex)

    files: dict[str, bytes] = {}
    split_ids: dict[str, list[str]] = {"dev": [], "test": []}
    twins: dict[str, list[dict]] = {"dev": [], "test": []}
    manifest: list[dict] = []
    skipped: list[str] = []
    for t in templates:
        split = fam_split[t.family]
        for i in range(per_template or t.n):
            rng = random.Random(seed_int("conv", t.id, i))  # noqa: S311
            try:
                fills = fill_slots(t, i, rng, lex, combo_split, split)
            except EmptyPool as exc:
                if not mock:
                    raise
                skipped.append(str(exc))
                break
            gold, tr, tw = build_conversation(t, i, fills, split, table)
            cid = gold["conversation_id"]
            gp, tp = f"data/gold/{cid}.json", f"data/transcripts/gold/{cid}__gold.json"
            files[gp], files[tp] = _dump(gold), _dump(tr)
            manifest += [
                _manifest_row(gp, files[gp], split, None),
                _manifest_row(tp, files[tp], split, cid),
            ]
            split_ids[split].append(cid)
            twins[split] += tw
    for s in ("dev", "test"):
        p = f"data/twins/twins_{s}.jsonl"
        files[p] = _jsonl(sorted(twins[s], key=lambda r: r["twin_id"]))
        manifest.append(_manifest_row(p, files[p], s, None))
        files[f"data/splits/{s}.txt"] = ("\n".join(sorted(split_ids[s])) + "\n").encode("utf-8")
    plan = {
        "generator_version": VERSION,
        "seed": SEED,
        "families": {s: sorted(f for f, v in fam_split.items() if v == s) for s in ("dev", "test")},
        "dosed_drug_combinations": {
            s: [
                list(c)
                for c in sorted(combo_split, key=lambda c: (c[0], c[2], float(c[1])))
                if combo_split[c] == s
            ]
            for s in ("dev", "test")
        },
        "rule": "template families and dosed drug-dose combinations are split-exclusive; "
        "bare drug mentions without a dose may occur in both splits",
    }
    files["data/splits/split_plan.json"] = _dump(plan)
    manifest.sort(key=lambda r: r["file"])
    files["data/manifest.jsonl"] = _jsonl(manifest)

    locked = {
        p: sha256_bytes(b)
        for p, b in files.items()
        if (
            p.startswith(("data/gold/", "data/transcripts/gold/"))
            and Path(p).stem.removesuffix("__gold") in set(split_ids["test"])
        )
        or p in ("data/twins/twins_test.jsonl", "data/splits/test.txt")
    }
    new_lock = lock_text(
        locked,
        f"FROZEN TEST SPLIT. sha256 of every test file and gold label.\n"
        f"generator {VERSION}, seed {SEED}. Format: <sha256>  <path>. "
        f"Rebuild only with `--refreeze` + a decision entry.",
    )
    lock_path = out_root / "data" / "splits" / "test.lock"
    if lock_path.exists() and lock_path.read_text(encoding="utf-8") != new_lock and not refreeze:
        raise GenerationError(
            "the regenerated TEST split differs from the frozen data/splits/test.lock. "
            "Refusing to overwrite. Pass --refreeze only with a decision entry."
        )
    files["data/splits/test.lock"] = new_lock.encode("utf-8")

    # write: overwrite changed files only, then remove stale generated files
    for rel, content in files.items():
        p = out_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not (p.exists() and p.read_bytes() == content):
            _retry(lambda p=p, c=content: p.write_bytes(c))
    for sub, pat in (
        ("data/gold", "*.json"),
        ("data/transcripts/gold", "*.json"),
        ("data/twins", "*.jsonl"),
    ):
        d = out_root / sub
        if d.exists():
            for p in d.glob(pat):
                if p.relative_to(out_root).as_posix() not in files:
                    _retry(p.unlink)

    meds = Counter()
    for s, ids in split_ids.items():
        for cid in ids:
            meds[s] += len(json.loads(files[f"data/gold/{cid}.json"])["gold_record"]["medications"])
    return {
        "conversations": sum(len(v) for v in split_ids.values()),
        "dev": len(split_ids["dev"]),
        "test": len(split_ids["test"]),
        "dev_medications": meds["dev"],
        "test_medications": meds["test"],
        "twins": {s: len(v) for s, v in twins.items()},
        "skipped": skipped,
    }
