"""
Build the presentation deck: docs/final/presentation.pptx
=========================================================

WHY THIS FILE EXISTS
--------------------
The final presentation (12-15 minutes) must cover, in the brief's order: the problem,
the architecture, a live demo, traces/logs, a real failure, and the safety controls.
This script writes an editable PowerPoint deck with that structure, so the content is
versioned in Git and can be rebuilt after a change instead of being edited by hand
in five copies.

WHAT YOU GET
------------
  - 18 slides, 16:9, in the web UI's colours (navy #1B2A5B, orange #F5A100)
  - speaker notes on every slide (what to say, about 45 seconds each)
  - grey dashed "INSERT: ..." boxes where a groupmate must add a screenshot or diagram.
    If the matching file already exists in docs/images/, the picture is placed instead.
    The full list is docs/final/PLACEHOLDERS.md.

All numbers on the slides are the verified figures from AGENTS.md, the failure catalogue
and the regression run of 23 Oct 2026 - nothing is computed or invented here.

Usage (PowerShell, repo root):
  pip install -r requirements-docs.txt
  py scripts\\build_slides.py
Then open docs\\final\\presentation.pptx in PowerPoint (or upload it to Google Slides).

Owner: Boonabaana Bronia, built with Claude Code.
"""

# ---------------------------------------------------------------------------
# Imports and constants
# ---------------------------------------------------------------------------
from pathlib import Path

from pptx import Presentation                          # pip install python-pptx
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "final" / "presentation.pptx"
IMAGES = ROOT / "docs" / "images"

NAVY = RGBColor(0x1B, 0x2A, 0x5B)
ORANGE = RGBColor(0xF5, 0xA1, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY_TEXT = RGBColor(0x5B, 0x64, 0x78)
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
SOFT_BLUE = RGBColor(0xE8, 0xEC, 0xF5)
W, H = Inches(13.333), Inches(7.5)                     # 16:9


# ---------------------------------------------------------------------------
# Small drawing helpers (each slide below is built from these)
# ---------------------------------------------------------------------------
def _text(frame, lines, size=20, color=NAVY, bold_first=False, bullet=True):
    """Fill a text frame with lines. A line starting with '  ' is a sub-point."""
    frame.word_wrap = True
    frame.clear()
    for i, line in enumerate(lines):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        sub = line.startswith("  ")
        text = line.strip()
        para.text = (("– " if sub else "• ") if bullet else "") + text
        para.level = 1 if sub else 0
        para.space_after = Pt(6)
        for run in para.runs:
            run.font.size = Pt(size - 3 if sub else size)
            run.font.color.rgb = GREY_TEXT if sub else color
            run.font.bold = bold_first and i == 0


def _box(slide, x, y, w, h, fill=None, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
    shape.shadow.inherit = False
    return shape


def new_slide(prs, title, notes, kicker=""):
    """A content slide: navy title band with an orange accent line, plus speaker notes."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])            # 6 = blank layout
    _box(slide, 0, 0, W, Inches(1.15), fill=NAVY)
    _box(slide, 0, Inches(1.15), W, Inches(0.06), fill=ORANGE)
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.9))
    tf = tb.text_frame
    tf.text = title
    tf.paragraphs[0].runs[0].font.size = Pt(32)
    tf.paragraphs[0].runs[0].font.bold = True
    tf.paragraphs[0].runs[0].font.color.rgb = WHITE
    if kicker:                                                   # small orange label, top right
        kb = slide.shapes.add_textbox(Inches(9.3), Inches(0.38), Inches(3.6), Inches(0.5))
        kb.text_frame.text = kicker
        p = kb.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        p.runs[0].font.size = Pt(14)
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = ORANGE
    slide.notes_slide.notes_text_frame.text = notes
    return slide


def bullets(slide, lines, x=0.6, y=1.5, w=12.1, h=5.6, size=22):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    _text(tb.text_frame, lines, size=size)
    return tb


def placeholder(slide, label, file_name, x, y, w, h):
    """The picture if docs/images/<file_name> exists, otherwise a dashed 'INSERT' box."""
    image = IMAGES / file_name
    if image.exists():
        pic = slide.shapes.add_picture(str(image), Inches(x), Inches(y), width=Inches(w))
        if pic.height > Inches(h):                               # keep inside the area
            ratio = Inches(h) / pic.height
            pic.height, pic.width = Inches(h), int(pic.width * ratio)
        return pic
    box = _box(slide, Inches(x), Inches(y), Inches(w), Inches(h), fill=LIGHT, line=GREY_TEXT)
    box.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    box.line.width = Pt(1.5)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.text = f"INSERT: {label}"
    tf.add_paragraph().text = f"save as docs/images/{file_name} · owner: ______"
    for i, para in enumerate(tf.paragraphs):
        para.alignment = PP_ALIGN.CENTER
        for run in para.runs:
            run.font.size = Pt(18 if i == 0 else 12)
            run.font.bold = i == 0
            run.font.color.rgb = RGBColor(0xB0, 0x00, 0x20) if i == 0 else GREY_TEXT
    return box


def table(slide, rows, x, y, w, col_widths=None, size=14, row_h=0.42):
    """A simple table; the first row is the header."""
    shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y),
                                   Inches(w), Inches(row_h * len(rows)))
    tbl = shape.table
    if col_widths:
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = str(value)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (SOFT_BLUE if r % 2 else WHITE)
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(size)
                    run.font.bold = r == 0
                    run.font.color.rgb = WHITE if r == 0 else NAVY
    return shape


def full_navy(prs, lines, notes):
    """Title / closing slide: navy background, big white text, orange accent."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _box(slide, 0, 0, W, H, fill=NAVY)
    _box(slide, Inches(0.8), Inches(2.0), Inches(1.6), Inches(0.08), fill=ORANGE)
    tb = slide.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(11.7), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, (text, size, color, bold) in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = text
        para.space_after = Pt(10)
        for run in para.runs:
            run.font.size, run.font.color.rgb, run.font.bold = Pt(size), color, bold
    slide.notes_slide.notes_text_frame.text = notes
    return slide


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------
def build() -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1. Title
    full_navy(prs, [
        ("SME Procurement Assistant", 44, WHITE, True),
        ("AI supports, never decides.", 26, ORANGE, True),
        ("An agentic procurement assistant for a Ugandan stationery shop", 22, WHITE, False),
        ("BSE4104 Emerging Trends in Software Engineering · Makerere University · October 2026", 16, WHITE, False),
        ("Team: Mwesigwa Arnold Mugahi · Boonabaana Bronia · [name] · [name] · [name]", 16, WHITE, False),
    ], "Presenter: [name]. Introduce the team and the one-line idea: an assistant that prepares "
       "procurement paperwork for a small shop, where every money decision stays with a human. "
       "(~30 s)")

    # 2. The problem
    s = new_slide(prs, "The problem", "Presenter: [name]. Tell the story: the shop's stock lives in an "
                  "exercise book. If it is lost or water-damaged, nobody knows what is low, how much to "
                  "order or from whom. Supplier reps pressure junior staff to over-order. The goal is not "
                  "faster decisions; it is the shop's own numbers and rules, available and checkable. (~45 s)",
                  kicker="WHY")
    bullets(s, [
        "Stock records live in one exercise book: lost or water-damaged = the shop's memory is gone",
        "Nobody can say what is low, how much to order, or from which supplier",
        "Supplier reps pressure junior staff into over-ordering",
        "The shop's rules (who may approve what) live in one person's head",
        "Goal: make the numbers and rules available and checkable,",
        "  without letting a probabilistic model make money decisions",
    ])

    # 3. What we built
    s = new_slide(prs, "What we built", "Presenter: [name]. Walk the flow left to right. Data is synthetic "
                  "CSVs plus a 12-document policy corpus. The model chooses tools and explains; Python does "
                  "all the maths and rules; the output is a DRAFT that a human approves. (~45 s)",
                  kicker="SOLUTION")
    steps = ["Shop data\n(CSV + 12 policy docs)", "8 deterministic\ntools (Python)", "Bounded agent\n(Gemini chooses tools)",
             "DRAFT\nrequisition", "Human approves\nor rejects"]
    for i, label in enumerate(steps):
        x = 0.5 + i * 2.55
        b = _box(s, Inches(x), Inches(2.2), Inches(2.2), Inches(1.6), fill=SOFT_BLUE if i != 4 else ORANGE)
        b.text_frame.text = label
        b.text_frame.word_wrap = True
        for para in b.text_frame.paragraphs:
            para.alignment = PP_ALIGN.CENTER
            for run in para.runs:
                run.font.size, run.font.bold, run.font.color.rgb = Pt(17), True, NAVY
        if i < 4:
            a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.22), Inches(2.85), Inches(0.3), Inches(0.3))
            a.fill.solid(); a.fill.fore_color.rgb = NAVY; a.line.fill.background()
    bullets(s, ["Flags low stock, compares quotes, estimates reorder quantities, plans within a budget",
                "Answers policy questions from the shop's own documents, with citations",
                "Console app + web UI (Streamlit) over the same functions"], y=4.3, h=2.6, size=20)

    # 4. AI boundary
    s = new_slide(prs, "AI supports, never decides", "Presenter: [name]. This is the AI Boundary Matrix "
                  "(docs/requirements/ai-boundary-matrix.md). Stress the bottom rows: approval and payment are "
                  "not prompt rules, they are the ABSENCE of a tool. The model cannot do them even if it tries. (~45 s)",
                  kicker="BOUNDARY")
    table(s, [
        ["Capability", "AI (model)", "Python (deterministic)", "Human"],
        ["Low-stock flagging", "chooses the tool, explains", "stock <= reorder point", "sets reorder points"],
        ["Reorder quantity", "explains the working", "ceil(avg x 1.5) - stock, MOQ", "sets qty when no history"],
        ["Policy questions", "answers only from retrieved text", "BM25 retrieval, citation check", "maintains documents"],
        ["Draft requisition", "decides which items", "lines, totals, +/-10% band", "-"],
        ["APPROVAL", "NEVER (no such tool)", "typed confirmation, audit log", "APPROVES / REJECTS"],
        ["ORDERING / PAYMENT", "NEVER (no such tool)", "no integration exists", "orders and pays offline"],
    ], 0.5, 1.55, 12.3, [2.6, 3.1, 3.7, 2.9], size=15, row_h=0.62)

    # 5. Architecture
    s = new_slide(prs, "Architecture: an AI shell around a deterministic core", "Presenter: [name]. Use the "
                  "diagram. Every request goes through src/llm_client.py (one fallback chain) and every tool "
                  "call through registry.execute_tool (allow-list, argument validation, trusted context, trace). "
                  "The worst the model can do is explain a correct draft badly. (~60 s)", kicker="ARCHITECTURE")
    placeholder(s, "Architecture / context diagram (Figure 1 of the report)", "fig1-context.png", 0.5, 1.5, 7.6, 5.6)
    bullets(s, ["UI: console + Streamlit", "Agents: tool_agent, restock_agent", "Gate: registry allow-list",
                "Tools: 8, all Python", "State: SQLite (drafts, audit, FSM, memory)", "Model: Gemini 3.8 Flash + 5 fallbacks"],
            x=8.4, y=1.6, w=4.5, h=5.4, size=18)

    # 6. Model and prompts
    s = new_slide(prs, "Model and prompt engineering", "Presenter: [name]. Model: gemini-3.8-flash with a "
                  "5-model fallback chain (free tier = 20 requests/day per model; 2.5-flash returns 404, F-06). "
                  "Prompts are versioned files (v1.0 -> v2.5) with tests. The key lesson: in Week 2 the model "
                  "got the arithmetic wrong under injection (F-04), so v2.0.0 moved ALL maths into tools. (~45 s)",
                  kicker="WEEK 2")
    table(s, [
        ["Version", "Change", "Result"],
        ["1.1.0", "first working prompt", "7/10 tests"],
        ["1.2.0", "only named, low items; formulas in code spans", "9/10 (checker tightened)"],
        ["2.0.0", "maths moved OUT of the prompt into tools (F-04)", "live agent 6/6"],
        ["2.2.0", "no draft claim without a real draft (F-13)", "regression 6/6"],
        ["2.5.0", "user roles removed (decision-001)", "current prompt"],
    ], 0.5, 1.55, 12.3, [1.6, 7.0, 3.7], size=16, row_h=0.55)
    bullets(s, ["F-04: the model wrote Erasers 70 (correct 63) and Staplers 114 (correct 88): no wording fixes arithmetic"],
            y=5.2, h=1.5, size=19)

    # 7. RAG
    s = new_slide(prs, "RAG: answers from the shop's own policies", "Presenter: [name]. 12 synthetic policy "
                  "documents, chunked by heading, BM25 index, score gate, top 3 plus the next section. Every claim "
                  "must cite a source id, and the code checks the ids. Unanswerable questions say 'not in the "
                  "documents'. Show R-4 honestly: keyword search cannot reason about number ranges. (~45 s)",
                  kicker="WEEK 3")
    placeholder(s, "RAG pipeline diagram (Figure 2 of the report)", "fig2-rag.png", 0.5, 1.5, 6.6, 5.5)
    bullets(s, ["12 documents, BM25 retrieval", "Citations checked in code", "No-answer handling",
                "hit@3 10/10, MRR 0.88", "15/15 grounded answers (live)", "R-4 open: numeric thresholds"],
            x=7.4, y=1.6, w=5.5, h=5.4, size=20)

    # 8. Tools and agent
    s = new_slide(prs, "Tools and the bounded agent", "Presenter: [name]. 8 tools, none can approve, order, "
                  "pay or contact anyone. The restock agent: preconditions -> SENSE (code) -> model chooses the "
                  "next tool -> registry runs it -> observe -> post-conditions -> STOP. Limits: 5 turns, 6 tool "
                  "calls, 3 allowed tools. The OUTCOME is decided by code, not by the model's wording. Read the "
                  "worked example numbers. (~60 s)", kicker="WEEKS 4-5")
    bullets(s, ["8 tools: low stock, quotes, reorder qty, plan within budget, draft,",
                "  inventory, purchase history, policy search",
                "Registry: allow-list -> schema validation -> trusted context -> run -> trace",
                "Restock agent: max 5 turns / 6 tool calls; outcome decided by code",
                "Worked example (all computed by tools):",
                "  10 of 15 items low · Bic Pens 65 · Rulers 57 · draft UGX 84,406",
                "  Budget UGX 300,000 -> 4 items, UGX 294,130"], size=21)

    # 9. Memory and state
    s = new_slide(prs, "Memory, state and interoperability", "Presenter: [name]. The workflow is an explicit "
                  "state machine: APPROVED can only be reached from AWAITING_APPROVAL, and only the human gate "
                  "does that. Drafts, audit events and sessions are stored in SQLite, scoped by shop and user; the "
                  "model can never choose its shop. Memory is justified (supplier preferences, feedback), never raw "
                  "chat. MCP server exposes the tools with permission levels. (~45 s)", kicker="WEEK 6")
    placeholder(s, "State machine diagram (Figure 3 of the report)", "fig3-state-machine.png", 0.5, 1.5, 6.6, 5.5)
    bullets(s, ["FSM: INITIALIZED -> ... -> AWAITING_APPROVAL -> APPROVED / REJECTED",
                "SQLite, scoped by shop + user", "Shop id injected by code, never by the model",
                "Justified memory with erasure", "MCP JSON-RPC server"], x=7.4, y=1.6, w=5.5, h=5.4, size=19)

    # 10. Web UI
    s = new_slide(prs, "The web UI", "Presenter: Bronia. The Streamlit UI calls the same functions as the "
                  "console; no new business logic. The status line (10 of 15 low) comes from get_low_stock(), not "
                  "from the model. Mention hosting (Render / Streamlit Cloud) and that the home screen needs no API "
                  "key. Replace the second box with the next screen once it is built. (~45 s)", kicker="UI")
    placeholder(s, "", "ui-home.png", 0.5, 1.5, 7.4, 5.6)
    placeholder(s, "Screenshot of the next UI screen (restock or review)", "ui-screen2.png", 8.2, 1.5, 4.6, 5.6)

    # 11. Live demo
    s = new_slide(prs, "Live demo", "Presenter: [name]. 1) Open the web UI / console. 2) Run a weekly restock "
                  "with UGX 300,000: show the timeline and the DRAFT. 3) Open Review drafts: the draft waits for a "
                  "human. 4) Ask the AI to approve it: it refuses, because no approve tool exists. 5) Approve it "
                  "yourself and show the audit entry. If the quota runs out, switch to the fallback screenshots. (~3 min)",
                  kicker="DEMO")
    bullets(s, ["Weekly restock, budget UGX 300,000 -> timeline + DRAFT",
                "Review drafts: it waits for a human",
                "Ask the AI to approve it -> refused (no such tool)",
                "Human approves -> audit event + state APPROVED"], w=6.3, size=20)
    placeholder(s, "Fallback screenshot: restock run", "fig6-restock-run.png", 7.1, 1.5, 5.8, 2.7)
    placeholder(s, "Fallback screenshot: approval + refusal", "fig7-approval-refusal.png", 7.1, 4.4, 5.8, 2.7)

    # 12. Traces and logs
    s = new_slide(prs, "Traces and logs: inspecting what the AI did", "Presenter: [name]. Open one trace file "
                  "and read a row aloud: run id, tool, arguments, status, latency. Every model call, every tool "
                  "call (allowed AND blocked), every human decision and every state transition is written by code, "
                  "not by the model. (~45 s)", kicker="OBSERVABILITY")
    bullets(s, ["llm_calls.jsonl: every model call (model, round, latency, outcome)",
                "tool_traces.jsonl: every tool call, allowed and blocked",
                "trace_T*.md: Sense -> Plan -> Act -> Observe -> Stop",
                "audit_events (SQLite): every human decision and edit",
                "state_transitions (SQLite): every workflow move"], w=6.4, size=19)
    placeholder(s, "Screenshot of a trace file (e.g. evidence/week5/trace_T2*.md or tool_traces.jsonl)",
                "slide-trace.png", 7.1, 1.5, 5.8, 5.6)

    # 13. A real failure: F-26
    s = new_slide(prs, "A real failure: F-26, the merge that hid every draft", "Presenter: Bronia. Two Week 6 "
                  "branches were merged; the tool saved drafts to SQLite while the approval screen still read JSON "
                  "files. The agent said 'draft created, awaiting approval', but the human saw nothing. Each branch "
                  "passed its own tests; only a full run after the merge exposed it. Fix: one scoped draft store. "
                  "Lesson: run every suite after every merge. Evidence: evidence/final/f26_*. (~60 s)",
                  kicker="FAILURE")
    table(s, [
        ["Offline suite", "Before the fix", "After the fix"],
        ["Week 4 tools", "20/22", "22/22"],
        ["Week 5 agent", "16/17", "17/17"],
        ["MVP", "5/7", "7/7"],
        ["Week 6 storage", "did not run", "9/9"],
    ], 0.5, 1.55, 6.6, [2.8, 1.9, 1.9], size=17, row_h=0.6)
    bullets(s, ["Symptom: AI said 'awaiting approval'; approval list was empty",
                "Cause: tool -> SQLite, approvals -> JSON files",
                "Fix: one scoped SQLite draft store",
                "Lesson: run ALL suites after EVERY merge",
                "Also shown: F-04 (wrong maths) -> maths moved to code"], x=7.4, y=1.6, w=5.5, h=5.4, size=18)

    # 14. Guardrails
    s = new_slide(prs, "Safety controls and guardrails", "Presenter: [name]. Map each brief requirement to the "
                  "code: permissions = allow-list (no approve/pay tool); validation = JSON Schema + input "
                  "guardrail; logs = the four trace streams; approval = human-only gate with typed confirmation; "
                  "tool limits = turn and call caps. These are code, not prompt instructions. (~45 s)", kicker="SAFETY")
    table(s, [
        ["Brief requirement", "How it is enforced (code)"],
        ["Permissions", "Tool allow-list; no approve / order / pay tool exists (F-07, F-19)"],
        ["Validation", "JSON Schema on every argument; input guardrail blocks injection; budget checks"],
        ["Logs", "Model, tool, decision and state-transition traces"],
        ["Approval controls", "Human-only gate, typed APPROVE / REJECT, reasons, audit; budget ceiling (F-12)"],
        ["Tool limits", "Max turns and tool calls, repeated-call guard, per-task tool list"],
        ["Shop isolation", "Shop/user injected by code; model-supplied shop rejected (F-25)"],
    ], 0.5, 1.55, 12.3, [3.0, 9.3], size=16, row_h=0.68)

    # 15. Evaluation
    s = new_slide(prs, "Evaluation results", "Presenter: [name]. 119 offline tests across nine suites, all "
                  "without the model, so anyone can verify the release without quota. 31 Week 7 scenarios cover "
                  "normal, edge, corrupted, adversarial, tool-failure and unauthorised-action cases. 26 failures are "
                  "documented with cause, fix and the test that proves it. (~45 s)", kicker="WEEK 7")
    table(s, [
        ["Measure", "Result"],
        ["Offline regression (9 suites, no API key)", "119 / 119"],
        ["Week 7 scenarios (6 categories)", "31 / 31"],
        ["RAG retrieval hit@3 / grounded answers", "10 / 10  ·  15 / 15"],
        ["Live agent / restock traces", "6 / 6  ·  4 / 4"],
        ["Documented failures (cause, fix, test)", "26 (23 closed)"],
    ], 0.5, 1.55, 12.3, [8.0, 4.3], size=18, row_h=0.7)

    # 16. Limitations
    s = new_slide(prs, "Limitations and future work", "Presenter: [name]. Be honest: R-4, two SQLite stores, "
                  "all shops share the same CSVs, no login, no CI, UI still being completed, free-tier quota. Then "
                  "the future-work list in priority order. (~45 s)", kicker="HONESTY")
    bullets(s, ["Keyword RAG cannot reason about number ranges (R-4)",
                "State split over two SQLite files; shops share the same CSV data",
                "No login (single trusted user, decision-001), no CI pipeline",
                "Free tier: 20 requests/day per model",
                "Next: approval_threshold tool, one database, finish + host the UI, CI after every merge"], size=21)

    # 17. Team and contributions
    s = new_slide(prs, "Team and contributions", "Presenter: [name]. One line per member about what they "
                  "built, and show the ClickUp board (tasks, owners, deadlines). Only list work each person "
                  "actually did. (~45 s)", kicker="TEAM")
    table(s, [
        ["Member", "Contribution"],
        ["Mwesigwa Arnold Mugahi", "AI Engineering Lead: model, prompts, tools, agents, RAG, FSM, MCP, evaluation"],
        ["Boonabaana Bronia", "Scoped SQLite storage, tenant isolation, F-26 fix, web UI, report and deck"],
        ["[name]", "[contribution]"],
        ["[name]", "[contribution]"],
        ["[name]", "[contribution]"],
    ], 0.5, 1.55, 7.4, [2.4, 5.0], size=13, row_h=0.6)
    placeholder(s, "ClickUp board screenshot (tasks, owners, deadlines)", "fig8-clickup.png", 8.2, 1.5, 4.7, 5.6)

    # 18. Q&A
    full_navy(prs, [
        ("Thank you", 44, WHITE, True),
        ("AI supports, never decides.", 26, ORANGE, True),
        ("Questions?", 28, WHITE, False),
        ("github.com/AJmight/Capstone_project-", 18, WHITE, False),
    ], "Presenter: [name]. Invite questions. Likely questions: why not let the model compute? (F-04); how do "
       "you know it cannot approve? (no tool + test O-15); what happens if the quota runs out? (fallback chain, "
       "offline tests); how are shops isolated? (shop id injected by code, F-25).")
    return prs


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    deck = build()
    deck.save(OUT)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(deck.slides)} slides)")
