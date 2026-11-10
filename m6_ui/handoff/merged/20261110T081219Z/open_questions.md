## m6_ui (2026-11-10)

1. **Human-confirmed flags can never be saved.** m5's `POST /records/{id}/save` refuses (409) whenever any verdict check flags. The UI lets a reviewer confirm a flagged value ("Yes, this is correct"), but the record then stays "approved, NOT saved" forever unless an edit makes the verifier pass. Is a reviewer override wanted (for example a `review.v1` contract carrying each flag's answer + reason, accepted by m5 with an audit entry)? Contract change needed; not done by m6.
2. **record_id vs m5 database UUID.** record.v1 `record_id` is not the id m5 uses in its URLs. m6 live mode uses a stop-gap JSON map (`M6_SERVER_IDS`). Should m5 expose a lookup by `record_id`?
3. **Kannada UI wording (UNVERIFIED, not native-validated):** all of `m6_ui/i18n/kn.json`.
4. **Conjunct rendering on Android/Linux (UNVERIFIED):** checked only in headless Edge on Windows.
5. **360 px layout (UNVERIFIED):** headless screenshots of the live Streamlit app were blank.
6. **Variable font support on old Android WebViews (UNVERIFIED).**
7. **Live mode end to end (UNVERIFIED):** HttpGate tested only with a fake HTTP transport; SubprocessVerifier only with a fake command.
