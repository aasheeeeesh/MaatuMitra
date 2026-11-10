"""Build and load data/lexicon/drugs.csv.

Build (needs the optional extra `data`: indic-transliteration 2.3.82, MIT):
    uv run --extra data python -m m1_data build-lexicon
Load (no extra needed): `load_lexicon()`.
"""

from __future__ import annotations

import csv
import difflib
import io
from dataclasses import dataclass, field
from pathlib import Path

from m1_data import kn
from m1_data.config import ROOT
from m1_data.lexicon_source import AWARE_URL, DRUGS, FETCHED, ISMP_EVIDENCE, ISMP_URL, NLEM_URL, fda

LEXICON_CSV = ROOT / "data" / "lexicon" / "drugs.csv"
CSV_COLUMNS = [
    "id",
    "generic_en",
    "kn_primary",
    "kn_variants",
    "roman_variants",
    "class",
    "aware_class",
    "nlem_listed",
    "strengths_mg",
    "adult_dose_range_mg",
    "max_daily_mg",
    "confusable_with",
    "source_url",
    "verified_by",
]
STEMS = ("cillin", "mycin", "floxacin", "cef", "ceph", "azole", "olone", "asone")
TRANSLIT_NOTE = (
    "Kannada spellings: ISO 15919 respelling by AI agent, converted with indic-transliteration "
    "2.3.82 (not native-validated)"
)


def _iso_to_kn(iso: str) -> str:
    from indic_transliteration import sanscript  # optional extra `data`

    return kn.nfc(sanscript.transliterate(iso, sanscript.ISO, sanscript.KANNADA))


def _stem_group(name: str) -> set[str]:
    return {s for s in STEMS if s in name}


def _confusables(d: dict) -> tuple[list[str], list[str]]:
    """Return (names, notes). ISMP-cited pairs first, then AI-proposed similar names."""
    names, notes = [], []
    for other in d["ismp"]:
        names.append(other)
        notes.append(f"{other}: ISMP ({ISMP_EVIDENCE.get((d['generic'], other), 'cited')})")
    heur = []
    for o in DRUGS:
        g = o["generic"]
        if g == d["generic"] or g in names:
            continue
        ratio = difflib.SequenceMatcher(None, d["generic"], g).ratio()
        if ratio >= 0.6 or (_stem_group(d["generic"]) & _stem_group(g)):
            heur.append((-ratio, g))
    for _, g in sorted(heur)[:4]:
        names.append(g)
    if heur:
        notes.append("others: AI-proposed name-similarity/shared-stem pairs (UNVERIFIED)")
    return names, notes


def build_rows() -> list[dict]:
    rows = []
    for i, d in enumerate(DRUGS, start=1):
        urls = []
        notes = [f"agent-fetched {FETCHED}"]
        if d["nlem"]:
            urls.append(NLEM_URL)
            notes.append(d["nlem_note"] + ("" if d["nlem"] == "yes" else " [UNVERIFIED strengths]"))
        else:
            notes.append("NLEM: " + d["nlem_note"] + " (UNVERIFIED)")
        if d["cls"] == "antibiotic":
            urls.append(AWARE_URL)
            notes.append(f"AWaRe={d['aware']} (WHO AWaRe portal)")
        lo_hi = mx = ""
        if d["label"]:
            lid, (lo, hi), max_daily, lnote, *more = d["label"]
            is_url = lid.startswith("https://")
            urls.append(lid if is_url else fda(lid))
            urls.extend(more[0] if more else [])
            lo_hi = f"{kn.fmt_num(lo)}-{kn.fmt_num(hi)}"
            mx = kn.fmt_num(max_daily) if max_daily else ""
            kind = "fetched web page" if is_url else "openFDA US label"
            notes.append(f"dose from {kind} {lid}: {lnote}")
            if not max_daily:
                notes.append("max_daily not stated in label (blank)")
        else:
            notes.append(f"dose UNVERIFIED: {d.get('label_note', 'no label fetched')}")
        urls.extend(d.get("extra_urls", []))
        if d.get("name_source"):
            urls.append(d["name_source"])
            notes.append("name/usage only: Kannada health page using 'ORS' (KN-4)")
        conf, cnotes = _confusables(d)
        if d["ismp"]:
            urls.append(ISMP_URL)
        notes += cnotes
        notes.append(TRANSLIT_NOTE)
        kn_primary = _iso_to_kn(d["iso"])
        kn_vars = [
            v for v in dict.fromkeys(_iso_to_kn(v) for v in d["iso_variants"]) if v != kn_primary
        ]
        rows.append(
            {
                "id": f"drug-{i:02d}",
                "generic_en": d["generic"],
                "kn_primary": kn_primary,
                "kn_variants": "|".join(kn_vars),
                "roman_variants": "|".join(d["roman"]),
                "class": d["cls"],
                "aware_class": d["aware"],
                "nlem_listed": "yes" if d["nlem"] else "UNVERIFIED",
                "strengths_mg": "|".join(kn.fmt_num(s) for s in d["strengths"]),
                "adult_dose_range_mg": lo_hi,
                "max_daily_mg": mx,
                "confusable_with": "|".join(conf),
                "source_url": "|".join(urls),
                "verified_by": "; ".join(notes),
            }
        )
    return rows


def csv_text(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def write_lexicon(path: Path = LEXICON_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(csv_text(build_rows()), encoding="utf-8", newline="\n")
    return path


# ---------------------------------------------------------------- loading for the generator

_HINTS = {d["generic"]: d for d in DRUGS}


@dataclass
class Drug:
    generic: str
    kn_primary: str
    kn_variants: list[str]
    roman: list[str]
    cls: str
    strengths: list[float]
    dose_range: tuple[float, float] | None
    form: str = "tablet"
    syrup_ml: list[float] = field(default_factory=list)
    freqs: list[int] = field(default_factory=lambda: [1, 2, 3])
    durs: list[int] = field(default_factory=lambda: [3, 5])

    @property
    def mg_doses(self) -> list[float]:
        if self.generic in {"amoxicillin-clavulanate", "cotrimoxazole"}:
            return []  # combination products: spoken as tablet counts only
        if self.strengths and self.dose_range:
            lo, hi = self.dose_range
            inter = [s for s in self.strengths if lo <= s <= hi]
            if inter:
                return inter
            return [lo]
        if self.dose_range:
            return [self.dose_range[0]]
        return list(self.strengths)

    def dosed_combos(self) -> list[tuple[str, float, str]]:
        out = [(self.generic, v, "mg") for v in self.mg_doses]
        if self.form in {"tablet", "capsule"}:
            out.append((self.generic, 1, self.form))
            if self.generic == "paracetamol":
                out.append((self.generic, 2, "tablet"))
        # paediatric liquid volumes (generator hint, synthetic, not dosing advice; REFREEZE-1)
        out += [(self.generic, v, "ml") for v in self.syrup_ml]
        return out


def _nums(s: str) -> list[float]:
    out = []
    for x in s.split("|"):
        x = x.strip()
        try:
            v = float(x)
        except ValueError:
            continue
        out.append(int(v) if v.is_integer() else v)
    return out


def load_lexicon(path: Path = LEXICON_CSV) -> dict[str, Drug]:
    lex = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            rng = None
            if r["adult_dose_range_mg"]:
                lo, hi = _nums(r["adult_dose_range_mg"].replace("-", "|"))
                rng = (lo, hi)
            h = _HINTS.get(r["generic_en"], {})
            drug = Drug(
                generic=r["generic_en"],
                kn_primary=r["kn_primary"],
                kn_variants=[v for v in r["kn_variants"].split("|") if v],
                # purely numeric aliases (e.g. "625") are lexicon aliases only; never spoken as a name
                roman=[v for v in r["roman_variants"].split("|") if v and not v.isdigit()]
                or [r["generic_en"]],
                cls=r["class"],
                strengths=_nums(r["strengths_mg"]),
                dose_range=rng,
            )
            if h:
                drug.form, drug.freqs, drug.durs = h["form"], h["freqs"], h["durs"]
                drug.syrup_ml = list(h.get("syrup_ml", []))
            elif r["class"] == "oral_rehydration":
                drug.form, drug.freqs, drug.durs = "sachet", [], []
            lex[drug.generic] = drug
    return lex
