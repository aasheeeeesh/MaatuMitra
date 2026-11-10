"""Coverage numbers for the generated text data (printed and saved to results/m1_data/).

Detected = the shared negation table's regexes fire somewhere in the conversation.
Declared = the template put that pattern there on purpose (primary pattern of a twin).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import regex
import yaml

from m1_data import kn
from m1_data.config import ROOT
from m1_data.negation import load_table
from m1_data.render import FORM_WORD, SYMPTOMS
from m1_data.templates import TEMPLATES_DIR, load_templates

REPORTED_TYPES = {
    "strong_whole_token",
    "suffix",
    "verb_lexicon_suffix",
    "soft_suffix",
    "compound",
    "cross_turn",
    "clause_splitter_punct",
    "clause_splitter_word",
}
DECLARABLE_TYPES = {
    "strong_whole_token",
    "suffix",
    "verb_lexicon_suffix",
    "soft_suffix",
    "compound",
}
RESULTS = ROOT / "results" / "m1_data"


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def compute_coverage(data_dir: Path = ROOT / "data") -> dict:
    table = load_table()
    ids = {
        s: (data_dir / "splits" / f"{s}.txt").read_text(encoding="utf-8").split()
        for s in ("dev", "test")
    }
    # entries marked `generate: false` (table v2, e.g. the negative-question cue NEG-S07) are
    # matched by readers but m1 does not have to produce them in >= 5 conversations
    gen = [e for e in table.entries if e.get("generate", True)]
    reported = [e["id"] for e in gen if e["type"] in REPORTED_TYPES]
    declarable = [e["id"] for e in gen if e["type"] in DECLARABLE_TYPES] + ["NEG-X01"]
    detected = dict.fromkeys(reported, 0)
    traps = Counter()
    per_split = {}
    for s, cids in ids.items():
        c = Counter()
        fams, cats = set(), Counter()
        for cid in cids:
            doc = json.loads((data_dir / "gold" / f"{cid}.json").read_text(encoding="utf-8"))
            turns = [t["text"] for t in doc["turns"]]
            tags = doc["tags"]
            c["conversations"] += 1
            c["with_negation"] += tags["has_negation"]
            c["with_trap_tokens"] += bool(tags["trap_tokens"])
            c["code_switched"] += tags["code_switched"]
            c["cross_turn_negation"] += tags["cross_turn_negation"]
            meds = doc["gold_record"]["medications"]
            c["medication_entries"] += len(meds)
            c["negated_medication_entries"] += sum(m["negated"] for m in meds)
            c["english_drug_name_conversations"] += any(
                kn.has_latin(m["gold_span"]["span_text"].split()[0]) for m in meds
            )
            c["turns"] += len(turns)
            fams.add(doc["template_family_id"])
            cats[doc["template_family_id"][0]] += 1
            for pid in table.detect_conversation(turns):
                if pid in detected:
                    detected[pid] += 1
            for tok in {t for t, _, _ in kn.tokens(kn.compare_copy("\n".join(turns)))} & set(
                table.traps
            ):
                traps[tok] += 1
        c["code_switched_fraction"] = round(c["code_switched"] / max(1, c["conversations"]), 4)
        per_split[s] = {
            **dict(c),
            "template_families": len(fams),
            "per_category": dict(sorted(cats.items())),
        }
    declared_sets: dict[str, set] = defaultdict(set)
    for s in ("dev", "test"):
        for tw in _read_jsonl(data_dir / "twins" / f"twins_{s}.jsonl"):
            declared_sets[tw["primary_pattern"]].add(tw["conversation_id"])
    declared = {pid: len(declared_sets.get(pid, ())) for pid in declarable}
    tot = Counter()
    for v in per_split.values():
        tot.update({k: x for k, x in v.items() if isinstance(x, int) and not isinstance(x, bool)})
    tot["code_switched_fraction"] = round(tot["code_switched"] / max(1, tot["conversations"]), 4)
    tot.pop("template_families", None)
    twin_counts = {
        s: len(_read_jsonl(data_dir / "twins" / f"twins_{s}.jsonl")) for s in ("dev", "test")
    }
    return {
        "negation_table_version": table.version,
        "totals": dict(tot),
        "per_split": per_split,
        "negation_patterns_detected": detected,
        "negation_patterns_declared": declared,
        "trap_token_conversations": {t: traps.get(t, 0) for t in table.traps},
        "minimal_pair_twins": twin_counts,
    }


# ---------------------------------------------------------------- attestation check


def attested_tokens(sources_md: Path = TEMPLATES_DIR / "SOURCES.md") -> dict[str, set[str]]:
    """Parse ```attested KN-n ... ``` blocks of SOURCES.md."""
    out = {}
    text = sources_md.read_text(encoding="utf-8")
    for m in regex.finditer(r"```attested (KN-\d+)\n(.*?)```", text, flags=regex.S):
        out[m.group(1)] = {t for t, _, _ in kn.tokens(kn.compare_copy(m.group(2)))}
    return out


def template_vocabulary() -> set[str]:
    texts = []
    for t in load_templates():
        texts += [turn["text"] for turn in t.turns]
        for spec in t.slots.values():
            texts += [f[k] for f in spec.get("forms", []) for k in ("neg", "pos")]
            texts += spec.get("choices", [])
    texts += list(SYMPTOMS.values()) + list(FORM_WORD.values())
    texts += ["ದಿನಕ್ಕೆ ಬಾರಿ ಸಾರಿ ದಿನ ದಿವಸ ಒಂದು ವಾರ ಎಂ.ಜಿ", " ".join(w for w, _ in kn.NUM_WORDS.values())]
    forms = yaml.safe_load((TEMPLATES_DIR / "_forms.yaml").read_text(encoding="utf-8"))["form_sets"]
    texts += [f[k] for fs in forms.values() for f in fs for k in ("neg", "pos")]
    vocab = set()
    for s in texts:
        s = regex.sub(r"\{[^}]*\}|\[\[[a-z]+\d*\||\]\]", " ", s)
        vocab |= {t for t, _, _ in kn.tokens(kn.compare_copy(s)) if kn.has_kannada(t)}
    return vocab


def unattested_report() -> dict:
    att = attested_tokens()
    allatt = set().union(*att.values()) if att else set()
    vocab = template_vocabulary()
    un = sorted(vocab - allatt)
    return {
        "note": "Kannada tokens used by templates that do NOT occur in any attested-token list of "
        "data/templates/SOURCES.md. AI-composed, UNVERIFIED: a native speaker must check them.",
        "template_vocabulary_size": len(vocab),
        "attested_in_fetched_sources": len(vocab & allatt),
        "unattested_count": len(un),
        "unattested": un,
    }


def write_reports(data_dir: Path = ROOT / "data", out_dir: Path = RESULTS) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cov = compute_coverage(data_dir)
    (out_dir / "coverage.json").write_text(
        json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    un = unattested_report()
    (out_dir / "unattested_tokens.json").write_text(
        json.dumps(un, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return cov
