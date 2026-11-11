from m3_extract import textnorm as tn


def find(lex, text):
    return [(m.drug, m.match_type) for m in lex.find(tn.tokenize(text))]


def test_exact_kannada_and_latin(full_lexicon):
    assert find(full_lexicon, "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg") == [("amoxicillin", "exact")]
    assert find(full_lexicon, "Azithromycin 500 mg") == [("azithromycin", "exact")]


def test_variants(full_lexicon):
    assert find(full_lexicon, "metro ಮಾತ್ರೆ") == [("metronidazole", "variant")]
    assert find(full_lexicon, "cetrizine ಒಂದು ಮಾತ್ರೆ") == [("cetirizine", "variant")]
    assert find(full_lexicon, "ಮೊಂಟೆಲುಕಾಸ್ಟ್ 10") == [("montelukast", "variant")]


def test_multi_token_names_longest_match(full_lexicon):
    assert find(full_lexicon, "ಇದು ಐರನ್ ಫೋಲಿಕ್ ಆಸಿಡ್ ಅಲ್ಲ") == [("iron-folic acid", "exact")]
    # REFREEZE-1 spelling (long vowel ಓ) is the lexicon's own form
    assert find(full_lexicon, "ಓ.ಆರ್.ಎಸ್ ಆಗಾಗ ಕುಡಿಸಿ") == [("ors", "exact")]
    # short-vowel ಒ is what ASR may write: accepted as an m3 variant (data/asr_variants.yaml)
    assert find(full_lexicon, "ಒ.ಆರ್.ಎಸ್ ಆಗಾಗ ಕುಡಿಸಿ") == [("ors", "variant")]
    assert find(full_lexicon, "ಒ ಆರ್ ಎಸ್ ಸ್ವಲ್ಪ") == [("ors", "variant")]
    assert find(full_lexicon, "ಓ ಆರ್ ಎಸ್ ಸ್ವಲ್ಪ") == [
        ("ors", "exact")
    ]  # same tokens as the dotted form
    assert find(full_lexicon, "oral rehydration salts ಆಗಾಗ") == [("ors", "variant")]
    assert find(full_lexicon, "co-amoxiclav") == [("amoxicillin-clavulanate", "variant")]


def test_edit_distance_one_on_latin_only(full_lexicon):
    # one letter dropped
    assert find(full_lexicon, "azithromycn ಮಾತ್ರೆ") == [("azithromycin", "edit1")]
    # two edits: no match
    assert find(full_lexicon, "azthromycn") == []
    # short Latin words are never fuzzy-matched
    assert find(full_lexicon, "OK mg") == []


def test_trap_words_are_not_drugs(full_lexicon):
    assert find(full_lexicon, "ಎಲ್ಲಾ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇವೆ, ಅಲ್ವಾ?") == []


def test_match_offsets(full_lexicon):
    text = "ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್"
    toks = tn.tokenize(text)
    (m,) = full_lexicon.find(toks)
    assert text[toks[m.start_tok].start : toks[m.end_tok - 1].end] == "ಪ್ಯಾರಸಿಟಮಾಲ್"
