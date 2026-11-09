---
name: frontend-design
description: Visual and interaction design rules for the MaatuMitra Streamlit review app (Kannada-first, low-literacy users, mobile-first, WCAG AA, never colour alone, flagged-first review, i18n files, bundled Noto Sans Kannada, avoiding the default-template look). Use when building or reviewing m6_ui.
---

# Frontend design for MaatuMitra (project-specific; written by the architect)

A `frontend-design` skill exists in the Claude plugin marketplace folder on the dev
laptop but is NOT installed for this project and would not travel with a clone, so this
project writes its own (decision in docs/DECISIONS_EXPLAINED.md).

## 1. Who and what

Users: ASHA workers, nurses, physicians, pharmacists on cheap Android phones, often
outdoors, many more comfortable reading Kannada than English. The app's one job: make a
dangerous extraction error impossible to miss before approval.

## 2. Hard rules (each is checked in review and, where possible, by AppTest)

1. Base font size >= 18 px; line height >= 1.5 for Kannada (tall matras and conjuncts).
2. Touch targets >= 48 x 48 px with >= 8 px gaps.
3. Text contrast >= 4.5:1 (WCAG AA); state colours also meet 3:1 against the background.
4. Works at 360 px width with no horizontal scroll; one column on phones.
5. Kannada/English toggle; EVERY string comes from `i18n/kn.json` / `i18n/en.json`
   (versioned); a test greps `.py` files for hard-coded Kannada (U+0C80..U+0CFF).
6. Never colour alone: every flag has colour AND an icon AND a text label
   ("ಪರಿಶೀಲಿಸಿ / Check" style, wording from i18n).
Plus: flagged fields FIRST; Approve disabled until every flag is confirmed or edited;
"play this part" uses audio_start..audio_end or says "no timing available"; big yes/no
tap buttons beside voice input.

## 3. Typography and Kannada rendering

- Bundle Noto Sans Kannada locally (static files); verify its licence on the official page
  (SIL OFL is expected: UNVERIFIED until fetched) and record it in docs/licences.md.
- Declare `font-family: "Noto Sans Kannada", system-ui, sans-serif` and load the font with
  `@font-face` from the bundled file; never from a CDN at runtime.
- Ship a rendering test page with tricky conjuncts and vowel signs (for example ಕ್ಷ, ಜ್ಞ,
  ಸ್ತ್ರೀ, ರ್ಕ, ಕ್ಕೆ, ಳ್ಳ, words with ZWNJ/ZWJ) and check them by eye on Windows, Android
  and Linux; record what you actually checked.
- Do not letter-space Kannada; do not use ALL CAPS styles on mixed text.

## 4. Spacing and layout

- 8 px spacing scale (8, 16, 24, 32). Generous padding inside cards (16-24 px).
- One primary action per screen, at the bottom, full width on mobile.
- Transcript with highlighted evidence on top; field list below; flagged items pinned first.

## 5. Avoid the generic default look

- Do not ship the stock Streamlit theme. Set a deliberate palette in `.streamlit/config.toml`
  + a small CSS file: one calm base colour, one strong attention colour reserved for
  flags, neutral surfaces. Test the palette for contrast.
- Replace emoji-as-UI with simple consistent icons (or text symbols) that pair with labels.
- Remove Streamlit chrome that confuses users (hamburger menu, "Deploy" button) where the
  config allows; keep the app bound to 127.0.0.1.
- Use real content (fixture Kannada records) in every screenshot, not lorem ipsum.

## 6. Security in the UI

Escape ALL transcript text before inserting highlight markup (XSS); never put tokens in
URLs; no secrets in the browser; handle the server-side "cannot save" refusal visibly.
