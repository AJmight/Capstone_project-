# Week 8 Engineering Trail — why each change was made

**Project:** SME Procurement Preparation Agent (BSE4104 Capstone)
**Author:** Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)
**Week:** 8 — Hardening, final release and demonstration (20 October 2026)
**Coding partner for this pass:** Kilo (AI assistant) on the local checkout; the Week 6 and Week 7 code itself was written with Google Antigravity CLI (`agy`).

This file exists so that every change in Week 8 can be explained in one sentence:
*what was broken, why it mattered, and why the fix is the fix we chose.*

---

## W8-1 — The MCP server could not call a tool at all (failure F-23)

**What was broken.** `src/mcp_interface.py` called

```python
result = execute_tool(tool_name, arguments, user_name="MCP_Client")
```

but the registry's real signature is `execute_tool(name, args, context, run_id)`, and it
returns a **tuple** `(result, status)`. So every genuine `tools/call` raised a
`TypeError`, which the generic handler turned into a JSON-RPC `-32000` "internal
error". The client could therefore *list* the tools but never *run* one.

**Why it mattered.** MCP is a Week 6 headline deliverable and the whole point of the
standard is that a client can call a capability. A server that cannot execute is a
demo, not a deliverable.

**Why it survived the tests.** The Week 6 suite tested the handshake (`initialize`),
the tool list (`tools/list`) and the *refusal* of an approval request — but never a
successful `tools/call`. The test suite had drawn a line just before the bug.

**The fix.** Use the real signature, pass the trusted context the registry expects
(`created_by`), and unpack the tuple. The registry's status (`ok`, `blocked`,
`invalid`, `tool_error`, `crashed`) is now reported to the client instead of being
hidden behind a generic protocol error, because a client that is told *blocked* can
do something sensible and a client that is told *internal error* cannot.

**Evidence.** `tests/test_week8_release_checks.py::test_tools_call_executes_a_real_tool`
calls `get_low_stock` through the server and checks the real low-stock list comes
back.

---

## W8-2 — The human approval never moved the workflow (failure F-24)

**What was broken.** `src/approvals.py::decide()` wrote the decision to the draft
file, appended the audit line and stored a memory — and never touched the Week 6
state machine. A session therefore stayed in `AWAITING_APPROVAL` forever, even
after a human had approved. The Week 6 claim "the workflow can only reach APPROVED
through a human" was true in the *graph* and false in the *system*.

**Why it mattered.** The FSM is the answer we give when a marker asks "how do you
prove the AI cannot skip the human?". If the human's own approval does not move the
state machine, the proof is only a diagram.

**Why it was not obvious.** The two components were written in different weeks by
different passes and never had a shared key. The link that already existed is the
`draft_id` the restock agent stores on the session row.

**The fix.** `StateManager.find_session_by_draft_id()` finds the session that
produced a draft; `decide()` then updates the session's `approval_status` and
transitions it to `APPROVED` or `REJECTED` with the approver's name in the reason,
so the transition is on the audit trail too. The decision is written to the draft
**before** the state transition, and a failure in the transition cannot lose the
human's decision — the FSM update is wrapped so that a state problem never
overturns a recorded approval.

**Evidence.** `test_approval_moves_the_session_to_approved`,
`test_rejection_moves_the_session_to_rejected`, and
`test_draft_without_a_session_is_still_decidable` (a draft made by the plain tool
agent has no session, and approval must still work).

---

## W8-3 — The MCP server let the model choose the tenant (failure F-25)

**What was broken.** The memory tools took `shop_id` from the **model's arguments**:
`arguments.get("shop_id")`. The Week 6 work had carefully partitioned every memory
query by `shop_id`, and the MCP surface handed the model the key to that partition.

**Why it mattered.** This is the exact leak Week 6 set out to prevent (F-17). A
model asked for `shop_b`'s memories would get them, and the isolation tests would
still pass because they tested the memory module, not the MCP surface.

**The fix.** The server *owns* its tenant: `MCPServer(shop_id=...)` is trusted
configuration, validated at construction with `InputGuardrail.validate_shop_id`
(so a hostile id never even opens the database), and a request that names a
different shop is refused with `TENANT_ISOLATION_VIOLATION`. The model can ask for
*this* shop's memory; it can never ask for another shop's.

**Evidence.** `test_cross_shop_memory_request_is_refused`,
`test_own_shop_memory_is_readable`,
`test_malicious_shop_id_is_rejected_at_construction`.

---

## W8-4 — The guardrails existed, but nothing called them (F-12, F-18, F-21)

**What was broken.** `src/guardrails.py` was a complete, tested module — and it was
only ever called by the tests. The console app sent the user's words straight to the
model, the restock agent never asked the budget guardrail, and the approval gate
never compared a draft with the budget that had been allocated.

**Why it mattered.** "We built guardrails" is only true if the running system uses
them. A guardrail that only the test suite calls is documentation with an
`assert` in it.

**The fix, in three places.**

1. `src/app.py` — the user's own words go through `InputGuardrail.validate_user_prompt`
   before the model is called, and the budget goes through `validate_budget`. This is
   the surface a marker will actually use.
2. `src/restock_agent.py` — the run asks `BudgetCeilingGuardrail` whether the exact
   draft total is inside the allocated budget. A breach becomes the outcome
   `BUDGET_CEILING_EXCEEDED` and the session is terminated; the draft is never
   handed over as "ready to approve".
3. `src/approvals.py` — the *exact* total above the allocated budget is refused
   outright (the human must edit a quantity first), and the advisory ±10% estimate
   band (User Story 8) that still reaches above the budget needs an explicit
   override reason, which is written to the audit log together with the band and
   the allocated budget.

**Why the band is not blocked outright.** The band is the honest uncertainty of the
estimate; blocking it would be dishonest in the other direction. The rule we chose
is: *the exact number is a ceiling, the band must be acknowledged*. That is also
the rule a real shop owner would accept.

**Evidence.** `test_budget_ceiling_guardrail_blocks_overage`,
`test_over_budget_draft_cannot_be_approved`, and the wiring regression guards
`test_app_calls_the_input_guardrail` and
`test_restock_agent_calls_the_budget_guardrail` (these last two check that the
wiring is not silently removed by a later edit).

---

## W8-5 — The failure catalogue was renumbered onto the canonical ids

**What was wrong.** The Week 7 draft of `docs/evaluation/failure-catalogue.md`
numbered its findings `F-01 … F-18` in a **new** order, so several ids meant
something different from what the Week 4 and Week 5 documents had always meant by
them (its `F-07` was "false draft claim"; everywhere else `F-07` is "the model
called a tool it was never given"). It also listed three Week 2 findings that have
no evidence anywhere in the committed Week 2 record.

**Why it mattered.** A failure catalogue is a piece of evidence. If the same id
means two different things in two documents, the catalogue cannot be used to answer
"what went wrong, and what did you do about it" — which is the only reason it
exists.

**The fix.** The catalogue is now re-based on the numbering the weekly evaluation
documents already use: `F-01 … F-16` keep their original meaning, so every
existing cross-reference in the repository is now correct again, and the findings
that are genuinely new (Weeks 6, 7 and 8) take `F-17 … F-25`. The three
unevidenced Week 2 claims were **removed**, not renumbered: a failure we cannot
reproduce is a hypothesis. Section 3.2 of the catalogue states this openly, because
a marker who spots the change should see that it was deliberate.

---

## W8-6 — Broken links in the Week 6 and Week 7 documents

**What was wrong.** The Week 6 and Week 7 documents were written on a WSL path
(`/mnt/c/Users/user/Capstone_project-/...`) and every internal link was a
`file:///mnt/c/...` absolute URL. On Windows, on GitHub and in a printed report
they all point nowhere.

**The fix.** A script rewrote every such link to a path relative to the document,
so the links work in a clone on any operating system.

---

## W8-7 — The release checks (`tests/test_week8_release_checks.py`)

**What was added.** 19 offline regression tests in four groups: the MCP contract
(F-23, F-25), the approval-to-FSM link (F-24), the guardrails in the runtime path
(F-12, F-18, F-21), and wiring guards that fail if the guardrails are ever
unhooked from the running system.

**Why they are written this way.** Every test uses a temporary database and a
temporary drafts folder, and closes its SQLite connections before the folder is
deleted — on Windows an open connection keeps the file locked, and the test would
fail in a way that has nothing to do with the code under test.

---

## W8-8 — The runtime database is not source

`data/procurement.db` (sessions, transitions, memory) is created on first run and
is rebuilt by any clean clone, so it is now in `.gitignore` together with its
WAL/SHM siblings. A marker who clones the repository gets the same behaviour and
no stale database.

---

## W8-9 — Documentation corrections

* `docs/ONBOARDING.md` — the viva questions now name the canonical failure ids,
  the `±10%` LaTeX artefact was fixed, the test counts were updated, and the
  Week 8 role table points at the new release checks.
* `docs/PROJECT_HANDOFF.md` — Weeks 6 and 7 are marked done with their test
  counts, the failure catalogue range is corrected, and Week 8 now shows the
  hardening pass and what is left.
* `docs/team/task-board.md` — cards AI-1…AI-5 are marked done with the artefact
  that proves it, and the Week 8 cards are updated to what actually remains.
* `README.md` — the week table, the module table, the test commands and the
  "where we are" paragraph were brought in line with the code.
* `AGENTS.md` — updated with the Week 8 state, the new modules and the rules that
  came out of the hardening pass.
