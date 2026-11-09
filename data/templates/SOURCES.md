# Sources for the Kannada sentence templates

All pages below were fetched by the data-scientist agent on **2026-11-09** (firecrawl,
directQuote mode). The templates were **written by an AI agent** using the constructions and
words attested in these pages; an LLM is never ground truth. **Nothing here is
native-validated.** Template `grounding:` fields point to the ids below.

| id | source (fetched 2026-11-09) | licence (as far as known) | what it grounds |
|---|---|---|---|
| KN-1 | https://en.wikipedia.org/wiki/Kannada_grammar | CC BY-SA 4.0 (Wikipedia; UNVERIFIED for this page) | negation: periphrastic verbal noun + ಇಲ್ಲ (example ಮಾಡುವುದಿಲ್ಲಾ), spoken -ಲ್ಲ on verbs, adverbial participle -ade "without having done" (māḍade); prohibitives: root + bēḍa, bāradu ("one should not"), kūḍadu (stronger); polite imperative -i, banni; conditional -are on the past stem (bandare, māḍidare), ಇಲ್ಲವಾದರೆ "if not" |
| KN-2 | https://kn.wikipedia.org/wiki/ಜ್ವರ | CC BY-SA 4.0 (UNVERIFIED for this page) | symptom words (ಜ್ವರ, ತಲೆನೋವು, ಮೈಕೈನೋವು, ಚಳಿ, ಸುಸ್ತು, ನೆಗಡಿ, ಕೆಮ್ಮು in ನಾಯಿಕೆಮ್ಮು, ಉಸಿರಾಟಕ್ಕೆ ... ತೊಂದರೆ), ಕಡಿಮೆ ಆಗಿ, ಇಲ್ಲದಿದ್ದರೆ, ಬಂದಿದ್ದರೆ, "ದಿನದಿನವೂ ಎರಡು ಸಾರಿ" (times per day), ದಿವಸ, ವಾರ, ಮಾತ್ರ, ಎಲ್ಲ, ಆದರೆ, ಮತ್ತು, ಅಥವಾ, ಪ್ರತಿಜೈವಿಕ, ತಕ್ಕಷ್ಟು ನೀರು ಕೊಡಬೇಕು |
| KN-3 | https://kannada.news18.com/news/national-international/kidney-damage-due-to-excessive-use-of-antibiotics-and-other-tablets-ach-ws-l-2494291.html | news article, all rights reserved: only single words and short phrases used, no sentences copied | ಮಾತ್ರೆ, ಆಂಟಿಬಯಾಟಿಕ್ (also with ZWNJ: ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳ), ವೈದ್ಯರ ಚೀಟಿ ಇಲ್ಲದೆ, ಸ್ವಯಂ ಔಷಧಿ ಬೇಡ, ತೆಗೆದುಕೊಳ್ಳಬಾರದು, ಬೇಕಾಗುವುದಿಲ್ಲ, ಮಾಡದೆ, ವೈರಲ್ ಸೋಂಕು, ಮಾಡುವಂತಿಲ್ಲ, ಆದ್ದರಿಂದ, ಲಕ್ಷಣಗಳು ಮುಂದುವರಿದರೆ, ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಬೇಕು, spoken ತಗೊಂಡ್ರೆ, ಜಾಸ್ತಿ |
| KN-4 | https://www.carehospitals.com/kn/blog-detail/how-to-prepare-oral-rehydration-solution-and-its-benifits/ | hospital blog, all rights reserved: single words only | ಅತಿಸಾರ, ವಾಂತಿ, ORS written in Latin inside Kannada text (code-switching), ಮಕ್ಕಳು, ಕೆಮ್ಮು ಮತ್ತು ಶೀತ, ದಿನಕ್ಕೆ, ತೆಗೆದುಕೊಳ್ಳಿ, ಕುಡಿಯುವುದು, ಧನ್ಯವಾದಗಳು |
| KN-5 | https://en.wikipedia.org/wiki/Kannada_script | CC BY-SA 4.0 (UNVERIFIED for this page) | digits ೦-೯ and their names (ondu, eraḍu, mūru, nālku, aidu, āru, ēḷu, enṭu, oṃbattu) |
| KN-6 | https://en.wiktionary.org/wiki/Category:Kannada_cardinal_numbers | CC BY-SA (Wiktionary; UNVERIFIED) | ಹದಿನಾಲ್ಕು (14) and other cardinal number entries |

Other inputs (NOT sources of Kannada text): the negation table
`.claude/skills/kannada-nlp/negation_table.yaml` (brief + architect hypotheses) and the
architect's fixtures (AI-written).

## Attested-token lists

The blocks below list Kannada words seen in the fetched pages (single words, typed from the
fetched text). `python -m m1_data coverage` compares every Kannada word used by the
templates with these lists and writes the words that are NOT attested to
`results/m1_data/unattested_tokens.json`. Those words are AI-composed and need a native check.

```attested KN-1
ಅವರು ಕೆಲಸ ಮಾಡುವುದಿಲ್ಲಾ ನೀನು ನಿಜ ಹೇಳಿದರೆ ಇಲ್ಲವಾದರೆ ಬದುಕಿದೆ ಬದುಕುವೆ ಕೆಟ್ಟೆ ಕೆಡುವೆ
```

```attested KN-2
ಜ್ವರ ತಲೆನೋವು ಮೈಕೈನೋವು ಬಳಲಿಕೆ ಬೇಸರ ಹಸಿವು ಇಲ್ಲದಿರುವುದು ಚಳಿ ಬರುತ್ತದೆ ಔಷಧಗಳಿಂದಲೋ ಕಡಿಮೆ
ಮಾಡಬಹುದು ಮಾತ್ರವಲ್ಲ ಸುಸ್ತು ಸಂಕಟ ನೀರು ಕೊಡಬೇಕಾದ್ದು ಅಗತ್ಯ ಇಲ್ಲದಿದ್ದರೆ ಆಗಿ ಹೆಚ್ಚು ತಕ್ಕಷ್ಟು ಈ
ಕಾಲದಲ್ಲಿ ಎಲ್ಲ ಜ್ವರಗಳಲ್ಲೂ ರಾತ್ರಿ ಆದರೆ ಬಂದಿದ್ದರೆ ಎರಡು ಸಾರಿ ದಿನದಿನವೂ ಮತ್ತು ನೆಗಡಿ
ನಾಯಿಕೆಮ್ಮು ಇಳಿಯಬಹುದು ಇಳಿಯುತ್ತ ಬಂದು ಔಷಧವಿಲ್ಲ ಕೊಡುತ್ತಿದ್ದರು ಪ್ರತಿಜೈವಿಕಗಳನ್ನು ಪ್ರತಿಜೈವಿಕ
ಕೊಡುವುದು ಉಸಿರಾಟಕ್ಕೆ ತೊಂದರೆ ರೋಗಿಗೆ ರೋಗಿ ನಾಲ್ಕು ವಾರಗಳು ಮೂರನೆಯ ವಾರದಲ್ಲಿ ದಿವಸಗಳ ಮಾತ್ರ ಇವೆ
ಆದಾಗ ಸೇವಿಸಿದಾಗ ಬರುವುದುಂಟು ಅಥವಾ ಅಲ್ಲ ಚಿಕಿತ್ಸೆ ರಕ್ತ ಪರೀಕ್ಷೆ ಸೋಂಕು ದೇಹದಲ್ಲಿ ಲಕ್ಷಣಗಳು
ಮಾಡಬೇಕಾದ ಆರೋಗ್ಯವಾಗಿರುವಂತೆ ಕಾಣಬಹುದು
```

```attested KN-3
ಮಾತ್ರೆಗಳನ್ನು ಜಾಸ್ತಿ ತಗೊಂಡ್ರೆ ವೈದ್ಯರ ಚೀಟಿ ಇಲ್ಲದೇ ಮಾರಿದ್ರೆ ನೋವು ನಿವಾರಕ ಆಂಟಿಬಯಾಟಿಕ್ ಸಲಹೆ ನೀಡಿದೆ
ಇಲ್ಲದೆ ಮಾರಾಟ ಮಾಡುವಂತಿಲ್ಲ ಸ್ವಯಂ ಔಷಧಿ ಬೇಡ ಮಾತ್ರೆಗಳು ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳ ಔಷಧಗಳನ್ನು ಬಳಸಿದರೆ
ವೈದ್ಯರು ಆಸ್ಪತ್ರೆಗಳು ಸರಿಯಾದ ಪ್ರಮಾಣದಲ್ಲಿ ಬಳಸಬೇಕು ತೆಗೆದುಕೊಳ್ಳುವಂತಿಲ್ಲ ಬಂದಾಗಲೆಲ್ಲ
ತೆಗೆದುಕೊಳ್ಳಬಾರದು ವೈರಲ್ ಸೋಂಕಿನಂತಹ ಸಂದರ್ಭಗಳಲ್ಲಿ ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳು ಬೇಕಾಗುವುದಿಲ್ಲ ಸಮಸ್ಯೆ
ತೆಗೆದುಕೊಳ್ಳುವ ಮೊದಲು ವೈದ್ಯರಿಗೆ ತಿಳಿಸಬೇಕು ಲಕ್ಷಣಗಳು ಮುಂದುವರಿದರೆ ಪುನಃ ಮಾಡದೆ ವೈದ್ಯರನ್ನು
ಸಂಪರ್ಕಿಸಬೇಕು ಮಾತ್ರೆ ಸೇವಿಸಿ ನೋಡಿ ನೀಡಬೇಕು ತಪ್ಪು ನೀಡಬಾರದು ಅಗತ್ಯವಿದ್ದರೆ ಬಳಸಿ ಸುರಕ್ಷಿತ
ಆದ್ದರಿಂದ ರೆಸಿಪಿ ತೆಗೆದುಕೊಳ್ಳುವುದನ್ನು ನಿಲ್ಲಿಸಿ ಪಡೆಯುವಂತೆ ಹೇಳಿದೆ ಸಲಹೆಯಲ್ಲಿ ಹೇಳಲಾಗಿದೆ
```

```attested KN-4
ಅತಿಸಾರ ವಾಂತಿಯಿಂದ ವಾಂತಿ ಮಗುವಿನ ವಯಸ್ಸು ಮಕ್ಕಳಲ್ಲಿ ಮಕ್ಕಳು ಕೆಮ್ಮು ಶೀತ ಕುಡಿಯಬಹುದೇ ಕುಡಿಯುವುದು
ಅಗತ್ಯವಿಲ್ಲ ನೀರಿನ ಪ್ರತಿದಿನ ಹೊಂದಿಲ್ಲದಿದ್ದರೆ ದಿನಕ್ಕೆ ಗಂಟೆಗೆ ತೆಗೆದುಕೊಳ್ಳಿ ಔಷಧಗಳನ್ನು ಸಾಮಾನ್ಯವಾಗಿ
ಸಹಾಯ ಮಾಡುತ್ತದೆ ಆರೋಗ್ಯ ಡೋಸೇಜ್ ಅನುಸರಿಸಿ ಧನ್ಯವಾದಗಳು ಮತ್ತು
```

```attested KN-5
೦ ೧ ೨ ೩ ೪ ೫ ೬ ೭ ೮ ೯
```

```attested KN-6
ಹದಿನಾಲ್ಕು ಹದಿನೈದು ಹದಿನಾರು ಹನ್ನೆರಡು ಹನ್ನೊಂದು ಇಪ್ಪತ್ತು ನೂರು ಸಾವಿರ
```

Note on number words: the Kannada-script words ಒಂದು ... ಏಳು come from the kannada-nlp skill
table; KN-5 confirms them only through romanisation (ondu, eraḍu, ...), so they are
counted as unattested in script form until a native speaker confirms.
