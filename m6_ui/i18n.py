"""UI strings. Every visible string lives in i18n/kn.json and i18n/en.json (versioned).

`t(key, lang, **fmt)` raises KeyError for a missing key: a missing string is a bug, not a
silent English fallback. Kannada strings are AI-drafted and NOT native-validated.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent / "i18n"
LANGS = ("kn", "en")
DEFAULT_LANG = "kn"
ROLES = ("asha", "nurse", "physician", "pharmacist")


@lru_cache(maxsize=4)
def load(lang: str) -> dict:
    if lang not in LANGS:
        raise ValueError(f"unknown language {lang!r}")
    return json.loads((DIR / f"{lang}.json").read_text(encoding="utf-8"))


def has(key: str) -> bool:
    return all(key in load(lang) for lang in LANGS)


def t(key: str, lang: str, raw: bool = False, **fmt) -> str:
    value = load(lang)[key]  # KeyError on purpose
    if not isinstance(value, str):
        raise KeyError(key)
    return value if raw or not fmt else value.format(**fmt)


def other(lang: str) -> str:
    return "en" if lang == "kn" else "kn"
