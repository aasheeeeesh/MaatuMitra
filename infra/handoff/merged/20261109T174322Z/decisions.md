### D-?: How the orchestrator runs the builder agents   (Phase B / orchestration / orchestrator / 2026-11-09)
- What we needed to decide: How to actually start the 14 "agents" described in the brief, and how to stop parallel agents from breaking each other's work.
- Options we considered: (1) Use the new files in .claude/agents/ as named subagent types. Pro: exactly what the brief describes. Con: Claude Code loads agent files when a session starts, so files created during this session may not be usable until a restart (we did not test this). (2) Start general-purpose agents and paste the role, rules and spec into each request. Pro: works now. Con: the agent-file settings (tool limits, model) are not enforced by the tool; they are only instructions. (3) Do everything in one agent. Pro: simple. Con: breaks the brief's independence rule and overloads one context.
- What we chose: Option 2. Each delegation message tells the agent to read its own .claude/agents/<name>.md file and infra/builder_rules.md first.
- Why: It works immediately and keeps the agent files as the single written spec. The trade-off is that "reviewers are read-only" is an instruction, not a hard lock, so the orchestrator checks `git status` after every reviewer run.
- What we actually did: Wrote infra/builder_rules.md (shared rules: environment, how to add packages without breaking the shared virtual environment, boundaries, no commits, handoff files). Started three builders in parallel: m1 text data, m4 verifier, m5 backend.
- What could go wrong / weaknesses: An agent could ignore an instruction (for example edit a file outside its folder). Mitigation: the orchestrator reviews `git status` and the diff before every commit. The shared virtual environment is a single point of failure: if one agent runs plain `uv sync`, other agents' packages disappear.
- What else could be done: Restart Claude Code so the .claude/agents/ files load as real subagent types with enforced tool lists; give each module its own virtual environment (costs disk, which is tight: ~12 GB free).
- How to change this decision later: Edit infra/builder_rules.md; use the agent names from .claude/agents/ directly in a new session.
- Status: done

### D-?: Splitting the data module (m1) into a text pass and an audio pass   (Phase B / m1_data / orchestrator / 2026-11-09)
- What we needed to decide: m1 has nine big steps (drug list, templates, generator, split, speech synthesis, public speech download, manifest, docs, `make data`). One agent doing all of it risks running out of context halfway.
- Options we considered: (1) One agent does everything. Pro: one owner. Con: likely to stop half-done. (2) Text pass first (drug list, templates, generator, split, lock, manifest for text), audio pass later (TTS voices, noise/speed variants, FLEURS real speech). Pro: the verifier and extractor can use real text data early; each pass is smaller. Con: the test lock must be extended when audio is added.
- What we chose: Option 2.
- Why: Text data is what the verifier (m4) and extractor (m3) need first. Audio is only needed by the speech-recognition module (m2).
- What we actually did: Started the text pass (task B1a in PROGRESS.md). The audio pass (B1b) starts after it, with the rule that it may only ADD lines to data/splits/test.lock, never change existing ones.
- What could go wrong / weaknesses: Adding audio to the lock later means the lock file changes once. We will record that change in git with its own commit and explain it here, so an auditor can see it was an addition, not an edit.
- What else could be done: Generate audio at the same time on a second machine or Colab.
- How to change this decision later: PROGRESS.md rows B1a/B1b.
- Status: done

### D-?: Who is the git author of the commits   (Phase A / repo / orchestrator / 2026-11-09)
- What we needed to decide: Which name appears on the commits the orchestrator makes.
- Options we considered: (1) The student's own git identity. Pro: they own the work. Con: it would say a human typed commits that an AI made. (2) A clearly labelled identity "MaatuMitra orchestrator <orchestrator@localhost>" plus a "Co-Authored-By: Claude" line. Pro: honest about who made each commit. Con: the student may want their own name on the history.
- What we chose: Option 2.
- Why: Honesty about AI-generated work (constraint 9). The student can still add their own commits on top.
- What we actually did: Commits use `git -c user.name="MaatuMitra orchestrator" -c user.email="orchestrator@localhost"`. The global git settings were not changed.
- What could go wrong / weaknesses: Some course platforms expect commits from the student's account. The history is local only, so this is easy to change before pushing.
- What else could be done: Rewrite the author with `git rebase --exec 'git commit --amend --reset-author --no-edit'` before pushing (only if the student wants that and understands what it does).
- How to change this decision later: Change the author on future commits; history rewrite is optional.
- Status: done
