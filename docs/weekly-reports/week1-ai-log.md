# AI Engineering Log — Week 1

Required by the brief (§6): declare AI tools, record material AI-assisted decisions, and show that
generated work was reviewed and tested before it was accepted.

> **Reconstructed on 22 Oct 2026.** This log was missing from the repository. It was written during
> the Week 8 release pass from what the Week 1 report, the committed Week 1 documents and the
> repository history actually show — **not** from a contemporaneous log, which was not kept that
> week. Where a detail is not recoverable from the repository, it is marked as *not recorded*
> rather than guessed. The project started its AI engineering log properly in Week 2
> (`week2-ai-log.md`), and every later week's log is contemporaneous.

**Week:** 1 (31 Aug – 4 Sept 2026) · **Project:** SME Procurement Support Agent
**AI Engineering Lead:** Mwesigwa Arnold Mugahi (23/U/24738/PS)

## AI tools used

Week 1 was a **documents-only week**: the charter, the 12 user stories with acceptance criteria,
the AI Boundary Matrix and the first context diagram. There was no code in the repository yet, so
**no model API was called at all in Week 1** — the Gemini integration (and the first prompt) is
Week 2 work.

| Tool | Used for |
|:---|:---|
| DeepSeek | Supervisor/teacher: reviewing the scope of the use case, the structure of the user stories and the boundary matrix |
| ChatGPT | Explaining the terms in the brief (agentic AI, AI-native, evaluation) and drafting/rewriting prose for the requirements documents |
| Google Gemini | **Not used in Week 1** — the project had no code and no key yet; it enters in Week 2 |

## Material AI-assisted decisions

| # | Decision / artefact | AI source | Human review & verification |
|:---:|:---|:---|:---|
| 1 | Use case selection (SME procurement preparation) | DeepSeek (options) | Human chose it after checking that synthetic data could be produced immediately and that the approval boundary is naturally human |
| 2 | "AI supports, never decides" as the project's core boundary | DeepSeek + ChatGPT (discussion) | Human wrote the AI Boundary Matrix; the rule survived unchanged through all eight weeks and is what the final report defends |
| 3 | 12 user stories with acceptance criteria | ChatGPT (draft structure) | Human rewrote them against the actual system as it was later built; story 3 was descoped (see `week1-report.md` §3) |
| 4 | Initial context diagram | ChatGPT (layout) | Human redrew it against the real components; the final version is `docs/architecture/context-diagram.md` |

## Things the AI got wrong (and how we caught them)

- The early drafts of the user stories used a grocery-shop example (sugar, dairy, cooking oil) that did
  not match the synthetic data we actually generated (stationery). Caught when the data was written in
  Week 2 — the stories were aligned in Week 3.
- A suggested default reorder quantity of 20 (for items with no purchase history) was rejected in the
  requirements stage because it invents data; the same rule was re-argued in Week 2 and again in the
  Week 7 evaluation, and the code still refuses to do it.

## Data handling

No data left the project in Week 1: the only inputs were the assignment brief and the team's own
notes. There were no API keys, no CSV files and no model calls. All data in the project is synthetic.

## What is *not* recorded

The exact prompts sent in Week 1 were not kept, and the dates of individual conversations are not
recoverable from the repository. This log therefore records the **decisions and their sources**, not
a verbatim transcript — the standard we set for ourselves in Week 2 and kept from then on.
