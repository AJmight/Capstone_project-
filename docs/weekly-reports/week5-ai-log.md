# AI Engineering Log — Week 5

**AI Engineering Lead:** Mwesigwa Arnold Mugahi (23/U/244738/PS)

## AI tools used (unchanged from Week 4)

Google Gemini (product model; proof-reading failing code), Claude Code (coding partner), DeepSeek
(supervisor/teacher), ChatGPT (concept explanations), GitHub Copilot (inline error fixes).

## Material AI-assisted decisions (Week 5)

| # | Decision / artefact | AI source | Human review & verification |
|:---:|:---|:---|:---|
| 1 | Task choice: weekly restock within a budget | Claude | Compared with single-step alternatives (trail §1); matches the brief's "genuinely multi-step" test |
| 2 | `plan_within_budget` greedy urgency rule | Claude | Hand-calculated 300,000 case (4 items, 294,130) matched; A-14 |
| 3 | Restock agent with explicit state, pre/post-conditions, code-decided outcome | Claude | 16 offline tests incl. deliberately misbehaving fake models |
| 4 | Fault injection for the failure/recovery trace | Claude | Marked `injected: true` in traces so evidence is honest |
| 5 | Output check against false draft claims | Claude, after the F-13 regression | A-16; Week 4 live 6/6 |
| 6 | Prompt v2.1.0 → v2.2.0 → v2.2.1 | Claude | Each change triggered by a recorded live failure (F-13, F-14) |

## Things AI got wrong (caught by tests or review)

- The model (gemini-3.6-flash, v2.1.0) presented a fake "awaiting approval" draft to a viewer (F-13).
- gemini-3.5-flash wrote the approval status line when no draft existed (F-14) — partly caused by a contradiction in Claude's own prompt wording.
- Claude's first offline fake model crashed on a blocked retry (fixed before the tests were recorded).

## Data handling

Synthetic data only. Restock drafts are local files in `data/drafts/` (git-ignored); traces contain
synthetic item data, tool arguments and results, never keys.
