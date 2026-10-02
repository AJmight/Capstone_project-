# AI Engineering Log — Week 4

**AI Engineering Lead:** Mwesigwa Arnold Mugahi (23/U/244738/PS)

## AI tools used on this project (declared per brief §6)

| Tool | How it is used |
|:---|:---|
| Google Gemini (AI Studio API) | The model under evaluation in the product; also used to proof-read code when it fails |
| Claude Code (Anthropic) | Coding partner: implementation, code review, tests, documentation, git operations |
| DeepSeek | Supervisor/teacher: weekly plans, step-by-step guides, draft code |
| ChatGPT (OpenAI) | Explains concepts that are unclear from DeepSeek's explanations |
| GitHub Copilot | Fixing inline errors in the editor |

## Material AI-assisted decisions (Week 4)

| # | Decision / artefact | AI source | Human review & verification |
|:---:|:---|:---|:---|
| 1 | Week 4 plan: 3 tools, agent loop, offline/live tests | DeepSeek guide | Reviewed against the brief and our code; 10 changes made before coding (trail §1) |
| 2 | 4th tool `draft_requisition` (totals in Python) | Claude | Without it the model would still sum costs (F-04); O-09 checks 84,406 |
| 3 | Gatekeeper registry with roles and argument validation | Claude | Offline tests O-15…O-20; live L-05 proved it necessary (F-07) |
| 4 | Human-only `approvals.py` | Claude | O-21, O-22; demonstration on a real draft left unapproved for a human |
| 5 | Prompt v2.0.0 (major bump) | Claude, following our change discipline | Live 6/6 |
| 6 | Exact `Fraction` arithmetic | Claude | O-02 compares every low item with an independent formula |

## Things AI got wrong (caught in review)

- DeepSeek's `max(ceil(raw), 1)` would order 1 unit of well-stocked items (F-09).
- DeepSeek's agent bypassed our model fallback (would fail on quota exhaustion).
- DeepSeek's tests would pass wrong answers (`qty > 0`, `"draft" in text`).
- Claude's first approval CLI computed the confirmation word wrongly (`REJECTE`, F-11).
- At runtime, Gemini requested a tool it had not been given (F-07) — blocked by code.

## Data handling

Only synthetic CSV data reaches Gemini, now only as tool results. Drafts are local files in
`data/drafts/` (git-ignored). Traces store tool arguments and results (synthetic data only), never keys.
