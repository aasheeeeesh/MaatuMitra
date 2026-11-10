"""pytest fixtures for m3_extract (helpers live in _helpers.py; importlib import mode)."""

import pytest

from m3_extract.tests._helpers import FIX_LEXICON, ROOT


@pytest.fixture(scope="session")
def fx_lexicon():
    from m3_extract.lexicon import load_lexicon

    return load_lexicon(FIX_LEXICON)


@pytest.fixture(scope="session")
def full_lexicon():
    from m3_extract.lexicon import load_lexicon

    return load_lexicon(ROOT / "data" / "lexicon" / "drugs.csv")
