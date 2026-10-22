# Week 1 Engineering Trail — what was done, in order, and why

**Author:** Mwesigwa Arnold Mugahi (23/U/24738/PS), AI Engineering Lead
**Week:** 1 (31 Aug – 4 Sept 2026) · **Consolidated into the repository:** 6 Oct 2026

> **Reconstructed on 22 Oct 2026.** This trail was missing from the repository. It was written during
> the Week 8 release pass from the Week 1 report and the committed Week 1 documents, so it records
> what the repository proves and marks the rest as *not recorded*. The trails for Weeks 2–8 were
> written while the work was happening and are contemporaneous.

---

## 1. Goal

Pick a use case that the brief allows, and write down — **before any code** — what the system will
do, who it serves, and where the AI must stop. The Week 1 brief deliverables are the charter, 8–12
user stories with acceptance criteria, the AI Boundary Matrix and an initial context diagram.

## 2. Design decisions

| Decision | Why | Alternative rejected |
|:---|:---|:---|
| SME procurement *preparation* (not ordering) | The data can be synthetic from day one, and the human approval boundary is natural, so the AI can never cause an irreversible financial act | Any use case with automatic side effects (payments, supplier contact) |
| "AI supports, never decides" as the project rule | Makes the safety claim testable in code, not just in a prompt | "AI recommends, human decides" said loosely without a mechanism |
| One shop, one trusted user (Decision-001, taken in Week 6) | Keeps the boundary that matters — between shops — and is implementable in eight weeks | Full role/permission system, which the brief does not require |
| 12 user stories with acceptance criteria | The brief asks for 8–12; every story must be checkable by a test | Stories without acceptance criteria (not verifiable) |
| Write the context diagram before the code | Forces the boundary question early, when it is cheap to change | Diagramming the system after it exists |

## 3. Step-by-step build log

| # | Step | Artefact | Check performed |
|:---:|:---|:---|:---|
| 1 | Selected the SME procurement-preparation use case from the brief's option list | `docs/requirements/project-charter.md` | Feasible with synthetic data; no real supplier or payment needed |
| 2 | Wrote the charter (problem, users, scope, success criteria) | `docs/requirements/project-charter.md` | Every claim checkable against data we can generate |
| 3 | Wrote 12 user stories with acceptance criteria | `docs/requirements/user-stories.md` | Each story has a testable acceptance criterion; story 3 later descoped |
| 4 | Wrote the AI Boundary Matrix (what the AI may do / must never do) | `docs/requirements/ai-boundary-matrix.md` | No row permits approving, ordering, paying or contacting a supplier |
| 5 | Drew the first context diagram (shop → assistant → data and policy sources) | `docs/architecture/context-diagram.md` | Every arrow maps to a component that later existed |
| 6 | Set up the GitHub repository | repository history | First upload 2026-09-08 |
| 7 | Consolidated the Word documents into markdown in the repository | `docs/requirements/` | 6 Oct 2026; stories realigned to the stationery data |

## 4. What changed later, and why

| Original | Now | Why |
|:---|:---|:---|
| Grocery examples (sugar, dairy, cooking oil) in the early stories | Stationery examples | The synthetic data is stationery (`src/generate_synthetic_data.py`); a requirement that contradicts the data is a broken requirement |
| Story 3 (sales forecasting) | Descoped | No sales data exists — purchase history is a proxy, not sales. Better descoped than faked |
| "Viewer" role in the first draft of the stories | One trusted user per shop (Decision-001) | Removed in Week 6; the meaningful separation is between shops, and the code enforces it (`src/memory.py`, `src/state.py`) |
| Week 1 documents only existed as `.docx` | Markdown in `docs/requirements/` | A marker should not have to open Word to review the requirements |

## 5. What was not recorded

- The individual prompts used in Week 1 were not kept; the AI log for this week
  (`week1-ai-log.md`) is therefore a reconstruction from the committed documents.
- ClickUp was named as the board tool in the brief; the board itself was set up later
  (see `docs/team/task-board.md`).
- The Week 1 contribution table was left as `[to be completed by the team]` and is **still open**
  (board card PR-3) — the rule in `AGENTS.md` is that nobody's contribution is recorded unless
  they did it, so it stays empty until the team fills it in.
