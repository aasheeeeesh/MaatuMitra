"""Respell Latin-script words in gold text as Kannada script, for the TTS input only.

indic-tiny-tts-kannada reads Kannada script and silently skips Latin letters, which would make
the audio disagree with the gold text. The GOLD text is never changed; the respelled string is
stored next to the audio as `tts_input` so the audio is traceable. Spellings: drugs come from
data/lexicon/drugs.csv (kn_primary); other words are a small hand table (AI-composed guesses at
how people say them, not native-validated). A word that is in neither raises KeyError, so a new
template word can never be silently dropped from the audio.
"""

from __future__ import annotations

import csv
import difflib
import re
from pathlib import Path

# non-drug English words that occur in gold text (hand table, not native-validated)
WORDS = {
    "antibiotic": "ಆಂಟಿಬಯಾಟಿಕ್",
    "course": "ಕೋರ್ಸ್",
    "tablet": "ಟ್ಯಾಬ್ಲೆಟ್",
    "fever": "ಫೀವರ್",
    "ok": "ಓಕೆ",
    "injection": "ಇಂಜೆಕ್ಷನ್",
    "mg": "ಮಿಲಿಗ್ರಾಂ",
    "ml": "ಮಿಲಿಲೀಟರ್",
    "ors": "ಓ.ಆರ್.ಎಸ್",
    "ifa": "ಐ.ಎಫ್.ಎ",
    "oral": "ಓರಲ್",
    "rehydration": "ರಿಹೈಡ್ರೇಷನ್",
    "salts": "ಸಾಲ್ಟ್ಸ್",
    "sulphate": "ಸಲ್ಫೇಟ್",
    "acid": "ಆಸಿಡ್",
    "iron": "ಐರನ್",
    "folic": "ಫೋಲಿಕ್",
}
_DOTTED = re.compile(r"\bO\.R\.S\b", re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]*[A-Za-z]|[A-Za-z]")
FUZZY = 0.85


def build_table(lexicon_csv: Path) -> dict[str, str]:
    table = dict(WORDS)
    with open(lexicon_csv, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            kn = row["kn_primary"]
            for k in [row["generic_en"], *row["roman_variants"].split("|")]:
                k = k.strip().lower()
                if k and re.fullmatch(r"[a-z\- ]+", k) and " " not in k:
                    table.setdefault(k, kn)
    return table


def _lookup(w: str, table: dict[str, str]) -> str:
    k = w.lower()
    if k in table:
        return table[k]
    if "-" in k and all(p in table for p in k.split("-")):
        return " ".join(table[p] for p in k.split("-"))
    close = difflib.get_close_matches(k, [t for t in table if len(t) >= 6], n=1, cutoff=FUZZY)
    if len(k) >= 6 and close:
        return table[close[0]]
    raise KeyError(f"no Kannada respelling for Latin word {w!r}: add it to tts_pronounce.WORDS")


def kannadify(text: str, table: dict[str, str]) -> str:
    text = _DOTTED.sub(table["ors"], text)
    return _WORD.sub(lambda m: _lookup(m.group(), table), text)
