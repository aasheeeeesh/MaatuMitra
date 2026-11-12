# data/templates

59 sentence templates in 9 categories (a)-(i) and 22 template families (`<category>_<name>__f<n>`).
Sources: `SOURCES.md`. Shared negation forms: `_forms.yaml`. AI-composed, not native-validated.

Mini-language (m1_data/render.py): `{D1.name|kn|en|dose|dose_tab|freq|dur}` drug slot,
`{S1.kn}` symptom, `{K1.kn|en}` count, `{AB}` word, `{N1}` negation slot (negative form or
its minimal-pair positive form), `{X1}` cross-turn answer (`ಇಲ್ಲ.`/`ಇಲ್ಲಾ.` vs `ಹೌದು.`),
`[[m1|...]]` gold-span marker. Slot types: drug, symptom, count, word, neg, xturn.

## gold.v2 metadata (added 2026-11-12, rendering unchanged)

Markers may be NESTED (evidence spans sit inside the main span). Extra medication-item keys, all
read by `m1_data/goldv2.py`; every medication item must declare its status:

| key | meaning |
|---|---|
| `status` or `status_neg` + `status_pos` | prescribed, already_taken, not_taken, advised_against, stopped_early, continue_existing, unknown. The pair is chosen by the item's `neg` slot. |
| `status_span` | marker of the words that say it (a verb, the ಇಲ್ಲ / ಹೌದು answer, ...). Required unless the status is `unknown`. |
| `formulation` + `formulation_span` | literal ಸಿರಪ್ / ಮಾತ್ರೆ / Tablet / injection in the template. Without it, the form word of the drug slot's dose text (reported by the renderer as span `<slot>.form`) is used. |
| `route` + `route_span` | explicit (e.g. oral from a "drink" verb); otherwise derived from the formulation: tablet, capsule, syrup -> oral; injection -> injection_unspecified; sachet or none -> null. |
| `as_needed` + `as_needed_span`, `food_timing` + `food_span`, `strength` {value, unit} + `strength_span` | only when the sentence says it. No shipped template states a strength. |

Marker `g1` = the word for child (ಮಗು...) = `patient_age_band` child. No marker = no label (null).
