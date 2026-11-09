# Glossary

Plain definitions of every technical word used in this project. Builders add terms through
`<module>/handoff/glossary.md` (format `- **Term**: definition`); terms already here are skipped.

- **AMR (antimicrobial resistance)**: when bacteria stop responding to antibiotics, often because antibiotics are overused or misused.
- **ASR (automatic speech recognition)**: software that turns speech audio into written text.
- **ASHA worker**: an Accredited Social Health Activist, a community health worker in India who visits households.
- **AWaRe**: the WHO grouping of antibiotics into Access, Watch and Reserve, by how carefully they should be used.
- **Bootstrap**: estimating uncertainty by re-sampling the data many times with replacement and recomputing the metric each time.
- **CER (character error rate)**: how many characters must be inserted, deleted or changed to turn the computer's text into the correct text, divided by the length of the correct text.
- **CI (confidence interval)**: a range that likely contains the true value; we use 95% intervals.
- **Code point**: one Unicode character number (for example U+0C95 is ಕ). Our text offsets count code points.
- **Code-switching**: mixing two languages in one sentence, for example English drug names inside Kannada speech.
- **Contract**: an agreed data format (here a JSON Schema plus a few extra rules) that two modules use to talk to each other.
- **Evidence (span)**: the exact piece of the transcript (start and end position plus the words) that supports one item in a record.
- **Extras (optional extras)**: groups of extra Python packages that are installed only when asked for, for example `uv sync --extra asr`.
- **Fail-closed**: when something goes wrong or is unclear, the system stops and asks a human instead of letting things through.
- **Fixture**: a small hand-made example file used for testing before real data exists.
- **Git Bash**: the bash command shell that comes with Git for Windows; our Makefile needs it on Windows.
- **Gold (gold standard)**: the known correct answer, used to score the system.
- **Grapheme cluster**: what a reader sees as one letter, which in Kannada can be several code points (a consonant plus vowel sign, for example ಕಿ).
- **Hook (Claude Code)**: a command that Claude Code runs automatically before or after a tool is used; it can block actions.
- **JSON Schema**: a standard way to describe what a JSON file must contain; "draft 2020-12" is the version we use.
- **Lexicon**: a word list with extra information; here, drug names with spellings, classes and dose ranges.
- **Lockfile**: a file listing the exact version of every package, so everyone installs the same thing (here `uv.lock`).
- **MAX_PATH**: the old Windows limit of 260 characters for a file path.
- **NFC (Unicode Normalization Form C)**: a standard way to store Unicode text so the same letters always have the same code points.
- **Pre-registration**: writing down hypotheses and pass/fail thresholds before running the experiment, so results cannot shape the rules.
- **RLS (row-level security)**: a PostgreSQL feature that decides, row by row, which rows a database user may see or change.
- **Rule of three**: if something failed 0 times in N tries, the 95% upper bound of its failure rate is about 3/N.
- **Secret scanning (gitleaks)**: a tool that searches code and git history for passwords or keys that should not be there.
- **Skill (Claude Code)**: a folder with a SKILL.md file that gives an agent extra instructions for a type of task.
- **Subagent (Claude Code)**: a separate AI helper with its own instructions and tool permissions, defined in `.claude/agents/<name>.md`.
- **Test split**: the part of the data kept aside and used only once, at the end, to measure the final result honestly.
- **TTS (text-to-speech)**: software that turns written text into spoken audio.
- **uv**: a fast Python package and environment manager that writes a lockfile.
- **UUID**: a long random identifier (like 1b4e28ba-2fa1-11d2-883f-0016d3cca427) that cannot be guessed, unlike 1, 2, 3.
- **venv (virtual environment)**: a private folder of Python packages for one project.
- **WER (word error rate)**: like CER but counted in whole words.
- **Wilson interval**: a good way to compute a confidence interval for a proportion (k successes out of n), even when k is 0 or n is small.
- **ruff**: a fast tool that checks Python code style and common bugs, and formats code.
<!-- GLOSSARY-END -->
