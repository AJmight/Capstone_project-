# Placeholders to fill before hand-in

The final report (`docs/final-report.md` → `final-report.docx` / `.pdf`) and the deck
(`presentation.pptx`) are complete apart from the items below. Each image placeholder
says exactly which file to create. **Save the image under that name in `docs/images/`,
then rebuild:**

```powershell
pip install -r requirements-docs.txt     # once
py scripts\export_report.py              # report: placeholder boxes are replaced by your images
py scripts\build_slides.py               # deck: INSERT boxes are replaced by your images
```

You can also paste images straight into the `.docx` / `.pptx`, but a rebuild overwrites
those files. Pick one way per file and tell the team.

Put your name in the **Owner** column when you take an item, and tick it when it is done.

## Images

| # | Where | What to insert | How to produce it | File to save | Owner | Done |
|:--:|:---|:---|:---|:---|:---|:--:|
| 1 | Report Fig 1 (§3.1) · Slide 5 | Architecture / context diagram | Copy the Mermaid block under Figure 1 in `docs/final-report.md` into https://mermaid.live → Actions → PNG | `docs/images/fig1-context.png` | | ☐ |
| 2 | Report Fig 2 (§5.2) · Slide 7 | RAG pipeline diagram | Same, Mermaid block under Figure 2 | `docs/images/fig2-rag.png` | | ☐ |
| 3 | Report Fig 3 (§7.1) · Slide 9 | Workflow state machine | Same, Mermaid block under Figure 3 | `docs/images/fig3-state-machine.png` | | ☐ |
| 4 | Report Fig 5 (Appendix M) | Tool-call sequence diagram | Same, Mermaid block under Figure 5 | `docs/images/fig5-tool-call.png` | | ☐ |
| 5 | Report Fig 6 (Appendix G) · Slide 11 | Live weekly-restock run (timeline + outcome) | `py src\restock_agent.py --budget 300000 --user "Demo"` (needs `GEMINI_API_KEY`), screenshot the terminal; or the web UI restock screen once built | `docs/images/fig6-restock-run.png` | | ☐ |
| 6 | Report Fig 7 (Appendix G) · Slide 11 | Draft waiting for approval + the AI refusing to approve | `py src\approvals.py list`, then `py src\tool_agent.py "Approve draft REQ-…"`; one screenshot with both | `docs/images/fig7-approval-refusal.png` | | ☐ |
| 7 | Report Fig 8 (Appendix N) · Slide 17 | ClickUp board (tasks, owners, due dates) | ClickUp → List or Board view → screenshot | `docs/images/fig8-clickup.png` | | ☐ |
| 8 | Slide 12 | A trace file | Open `evidence/week5/trace_T2_budget_replan.md` (or a line of `evidence/week4/tool_traces.jsonl`) and screenshot it | `docs/images/slide-trace.png` | | ☐ |
| 9 | Slide 10 | The next web UI screen | Screenshot once the next screen is built | `docs/images/ui-screen2.png` | | ☐ |

Figure 4 (the web UI home screen) is already done: `docs/images/ui-home.png`.

**Size:** use PNG, about 1600 px wide. The scripts scale images automatically and keep the
report body within the 8–12 page limit. After adding images, run `py scripts\export_report.py`
and check that the printed `references_start` is still page 13 or lower.

## Text

| Where | What to fill in | Owner | Done |
|:---|:---|:---|:--:|
| Report header table · Slide 1 | Group name/number; every member's name, reg no and role (Bronia's reg no and role too) | | ☐ |
| Report "Individual contributions" · Slide 17 | One row per member, with **only work they actually did**, plus a link (commit, PR or document) | | ☐ |
| Speaker notes, every slide | Replace `Presenter: [name]` with who presents that slide (12–15 minutes in total) | | ☐ |
| `docs/weekly-reports/week2-report.md`, `week4-report.md` | The remaining `[name]` / `[link]` rows | | ☐ |
| Every weekly report | The ClickUp link where it says `ClickUp: [link]` | | ☐ |

## Check before submitting

- [ ] `py scripts\export_report.py` prints `Figure placeholders still waiting for an image: 0`
- [ ] Report body ends by page 12 (`references_start` ≤ 13)
- [ ] No `[name]`, `[reg no]`, `[role]` or `[group name]` left: `git grep -n "\[name\]\|\[reg no\]\|\[role\]\|\[group name"`
- [ ] Deck opened in PowerPoint; every slide has a presenter in its notes
- [ ] The live demo was rehearsed once, and the fallback screenshots (slide 11) are in place in case the quota runs out
