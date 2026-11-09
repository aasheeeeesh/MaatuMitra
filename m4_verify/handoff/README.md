# m4_verify handoff

Do NOT edit root docs directly. Write your parts here; the orchestrator merges them with
`make merge-handoff MODULE=m4_verify` (infra/scripts/merge_handoff.py):

| file | merged into | format |
|---|---|---|
| decisions.md | docs/DECISIONS_EXPLAINED.md | `### D-?: <title>   (<Phase> / m4_verify / <agent> / <date>)` + the section 11 bullets; numbers are assigned on merge |
| glossary.md | docs/glossary.md | `- **Term**: plain definition` (terms already present are skipped) |
| ai_usage.md | docs/ai_usage.md | free markdown (agent, module, what it generated, what a human must check) |
| human_todo.md | HUMAN_TODO.md | `- [ ] ...` items with exact steps |
| open_questions.md | docs/open_questions.md | free markdown |
| licences.md | docs/licences.md | rows `\| item \| type \| licence \| URL fetched \| allowed for coursework \|` |

Merged parts move to `handoff/merged/<timestamp>/`.
