# Decision 001 — Single trusted user per shop (no user roles)

| Field | Value |
|:---|:---|
| **Date** | 2026-10-13 |
| **Decided by** | Mwesigwa Arnold Mugahi (AI Engineering Lead), as product owner for this decision |
| **Status** | Accepted and implemented (code, tests, prompt v2.5.0, corpus) |

## Context

Weeks 4–5 had three user roles: **viewer** (read-only), **staff** (read + draft) and **owner** (read + draft,
and the only one allowed to approve in the console app). In a small Ugandan shop, however, the person
using the system is normally the owner, or one trusted person they appoint, who both prepares and
approves purchases. Separating roles added complexity that does not match how SMEs work.

## Decision

- **No user roles.** Anyone with access to the system is treated as the shop's trusted user.
- **The AI still cannot approve, order or pay.** That boundary is between the *AI* and the *person*, not
  between people: there is no tool for those actions, the agent refuses such requests, and approving a
  draft remains a deliberate human step (`src/approvals.py` / app option 4) with a typed `APPROVE` /
  `REJECT` confirmation, reasons for rejections and over-cap lines, and an audit-log entry.
- **The real separation is between shops.** One shop's data must never reach another shop's session
  (e.g. John asks a question and receives my shop's stock or prices). This is the cross-user leak that
  matters; it is handled by shop isolation (see `data-protection-and-multi-user.md`).

## What changed

| Area | Before | After |
|:---|:---|:---|
| `src/tools/registry.py` | `ROLE_PERMISSIONS`, `tool_declarations_for(role)`, `execute_tool(name, args, role, …)`, `UNAUTHORIZED` error | `tool_declarations()`, `execute_tool(name, args, context, run_id)`; allow-list, argument validation, trusted context and trace kept; tools carry a `side_effect` note instead of a permission |
| `src/tool_agent.py` | `run_agent(…, role=…)` | no role; task allow-list (`allowed_tools`) kept |
| `src/restock_agent.py` | precondition "role may draft" | removed; budget precondition kept |
| `src/app.py` | login with role; only owner could edit/approve | login with name; the user reviews and approves |
| Prompt | v2.4.0 role wording | v2.5.0: no roles; refusals explain the user approves drafts themselves |
| Corpus | GDE-02 "Roles"; POL-01 "nobody may approve their own requisition" | GDE-02 "Who uses the assistant"; POL-01 "an AI draft is never an approval; the person must review and approve" |
| Tests | O-16 viewer permission; L-05 viewer asks to draft; A-12 viewer precondition | O-16 "no tool can approve, order or pay"; L-05 "use the approve tool" → refused; A-12 bad budgets only |

## What stays protected (and why the change is safe)

| Risk | Control that remains |
|:---|:---|
| AI approves, orders or pays | No such tool (allow-list), refusal rule, O-16 and L-04/L-05 tests |
| AI drafts the wrong items or wrong amounts | All maths in Python; post-conditions; output check (F-13) |
| AI claims a draft exists when it does not | `check_output()` |
| Someone without permission uses the system | **Access protection** — the device/app login. With no roles, controlling *who has access* is the key control (real login is planned for Weeks 6–7) |
| One shop sees another shop's data | Shop isolation (planned: `shop_id` injected from the login into every tool and search index) |

## Consequences

- Earlier findings F-07 (a viewer's model tried the draft tool) and F-13's original scenario (a viewer shown a
  fake draft) were real findings under the old design and stay in the history. F-13's code fix still applies
  to everyone, because any model can claim a draft that does not exist.
- Week 4–5 reports and evaluations are left unchanged as a record of what was true at the time.
- Business policy in the corpus may still name an owner and a supervisor (approval thresholds): that is shop
  policy about people, not a system role.

## Regression after the change (2026-10-13, prompt v2.5.0, updated corpus)

| Suite | Result | Notes |
|:---|:---:|:---|
| Week 4 offline | 22/22 | O-16 now proves no tool can approve/order/pay |
| Week 5 offline | 17/17 | A-12 bad budgets only; A-16 false draft claim without roles |
| MVP offline | 7/7 | |
| RAG retrieval (offline) | hit@3 10/10, MRR 0.88 | unchanged after the GDE-02 / POL-01 edits |
| Week 4 live | 6/6 | new L-05 "use the approve_requisition tool" → refused, nothing approved |
| Week 5 live traces | 4/4 | T1–T4 outcomes unchanged |
| MVP live | 6/6 | |
| RAG live | 14/15 | RP-03 failed **before reaching any model**: all six models were out of daily quota or returned 503/504 (infrastructure, not an answer failure). Retest RP-03 when the quota resets. |
