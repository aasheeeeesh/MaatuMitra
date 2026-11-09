# data/templates

59 sentence templates in 9 categories (a)-(i) and 22 template families (`<category>_<name>__f<n>`).
Sources: `SOURCES.md`. Shared negation forms: `_forms.yaml`. AI-composed, not native-validated.

Mini-language (m1_data/render.py): `{D1.name|kn|en|dose|dose_tab|freq|dur}` drug slot,
`{S1.kn}` symptom, `{K1.kn|en}` count, `{AB}` word, `{N1}` negation slot (negative form or
its minimal-pair positive form), `{X1}` cross-turn answer (`ಇಲ್ಲ.`/`ಇಲ್ಲಾ.` vs `ಹೌದು.`),
`[[m1|...]]` gold-span marker. Slot types: drug, symptom, count, word, neg, xturn.
