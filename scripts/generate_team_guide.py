r"""
generate_team_guide.py
Generates the comprehensive BSE4104 Group Mastery & Defense Guide in Word (.docx) format.
Integrates the complete curriculum from ai-engineering/notebooks with the 8-week capstone implementation.
Outputs to:
  - C:\Users\user\OneDrive\Desktop\BSE4104_Team_Guide.docx
  - docs/team/BSE4104_Team_Guide.docx
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def add_callout(doc, text, title="LESSON TAKEAWAY / EXAMINER TRAP", hex_bg="F0F4F8", hex_border="1F3964"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, hex_bg)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
    
    # Left border thick, others none
    tcPr = cell._element.get_or_add_tcPr()
    borders = parse_xml(f'''<w:tcBorders {nsdecls("w")}>
        <w:left w:val="single" w:sz="24" w:space="0" w:color="{hex_border}"/>
        <w:top w:val="none"/>
        <w:right w:val="none"/>
        <w:bottom w:val="none"/>
    </w:tcBorders>''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    r_title = p.add_run(f"📌 {title}: ")
    r_title.bold = True
    r_title.font.size = Pt(10.5)
    r_title.font.name = "Calibri"
    r_title.font.color.rgb = RGBColor(0x1F, 0x39, 0x64)
    
    r_text = p.add_run(text)
    r_text.font.size = Pt(10)
    r_text.font.name = "Calibri"
    r_text.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    # Add small spacing after callout
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(2)
    p_after.paragraph_format.space_after = Pt(4)

def format_table(table, col_widths, headers, data, header_bg="1F3964"):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Format header
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], header_bg)
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.bold = True
            r.font.size = Pt(9.5)
            r.font.name = "Calibri"
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            
    # Add data rows
    for r_idx, row_data in enumerate(data):
        row = table.add_row()
        cells = row.cells
        bg_col = "F9FAFB" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            cells[c_idx].text = str(val)
            set_cell_background(cells[c_idx], bg_col)
            set_cell_margins(cells[c_idx], top=80, bottom=80, left=120, right=120)
            p = cells[c_idx].paragraphs[0]
            for r in p.runs:
                r.font.size = Pt(9)
                r.font.name = "Calibri"
                r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
                
    # Set widths
    for row in table.rows:
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = Inches(width)

def build_guide():
    doc = docx.Document()
    
    # Page setup - 1 inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        
    # Styles setup
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(4)

    # ── DOCUMENT TITLE & METADATA ──
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(2)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("BSE4104: AI-NATIVE AGENTIC CAPSTONE")
    r_title.bold = True
    r_title.font.size = Pt(24)
    r_title.font.color.rgb = RGBColor(0x1F, 0x39, 0x64)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(6)
    r_sub = p_sub.add_run("Group Mastery & Viva Defense Guide: Lessons, Architecture, Role Explanations, & Q&A")
    r_sub.font.size = Pt(14)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(0x00, 0x70, 0x8A)

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_after = Pt(18)
    r_meta = p_meta.add_run("Makerere University · Department of Computer Science · Year IV Semester I (2026/2027)\nCourse Convener: Dr. Kamulegeya Grace B (PhD) · System Release: v1.0.0")
    r_meta.font.size = Pt(9.5)
    r_meta.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # Team roster table
    p_team_hdr = doc.add_heading("Project Team & Defense Responsibilities", level=2)
    p_team_hdr.paragraph_format.space_before = Pt(6)
    p_team_hdr.paragraph_format.space_after = Pt(4)
    
    tbl_team = doc.add_table(rows=1, cols=4)
    format_table(
        tbl_team,
        [2.2, 1.4, 2.0, 1.4],
        ["Student Name", "Reg Number", "Capstone Role", "Primary Ownership"],
        [
            ["Mwesigwa Arnold Mugahi", "23/U/24738/PS", "AI Engineering Lead", "Agent Loop, RAG, Prompts, Tools"],
            ["Boonabaana Bronia", "23/U/07647/EVE", "App Integration / Storage & UI Lead", "Storage Engine, Streamlit UI, F-26"],
            ["Nakyambadde Mariam", "23/U/13953/EVE", "Requirements & Documentation Lead", "User Stories, Boundary Matrix, Reports"],
            ["Naisanga Patricia", "23/U/13204/EVE", "Quality & Security Lead", "Guardrails, 119/119 Tests, F-Catalogue"],
            ["Tulinawe Ismail", "23/U/18058/EVE", "DevOps & Deployment Lead", "Reproducibility, Traces, SQLite Ops"],
        ]
    )

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    add_callout(
        doc,
        "Every single group member must read this entire guide. At evaluation, examiners will ask each member "
        "to explain code lines, architectural decisions, and failure root causes. If one member says 'I only wrote the report' "
        "or 'Arnold did the AI part,' the whole group is heavily penalized. This guide gives everyone the exact technical "
        "vocabulary, conceptual clarity, and code references needed to excel.",
        title="CRITICAL EVALUATION MANDATE"
    )

    # ════════════════════════════════════════════════════════════════════════════
    # PART I: FOUNDATIONAL AI ENGINEERING LESSONS
    # ════════════════════════════════════════════════════════════════════════════
    p_part1 = doc.add_heading("PART I: Foundational AI Engineering Lessons", level=1)
    p_part1.paragraph_format.space_before = Pt(16)
    
    doc.add_paragraph(
        "To defend this capstone convincingly, every member must understand the underlying science of agentic AI systems. "
        "These lessons are drawn directly from the AI engineering curriculum (referencing the formal curriculum notebooks in "
        "C:\\Users\\user\\ai-engineering\\notebooks) and map directly to the production code in our repository."
    )

    # --- LESSON 1 ---
    doc.add_heading("Lesson 1: Traditional Chains vs. Directed Graphs vs. Bounded ReAct Agents", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-1/01-chain.ipynb & 03-agent.ipynb\n\n"
        "1. Linear Chains: In a standard LLM chain, execution flows in a single forward pass: User Input -> Prompt Template -> Model -> Output Parser. "
        "Chains cannot adapt dynamically if data is missing, nor can they recover if an external service returns an error.\n"
        "2. Directed Graphs: Systems are modeled as nodes (units of computation) and edges (transitions). Execution is deterministic and verifiable.\n"
        "3. Bounded ReAct (Reason + Act) Agents: The agent operates in an iterative loop: SENSE (observe world state) -> PLAN (decide whether a tool is needed) -> "
        "ACT (execute deterministic tool) -> OBSERVE (ingest tool output into context) -> RE-PLAN / STOP. "
        "Crucially, our system implements a Bounded Agent (src/tool_agent.py & src/restock_agent.py). "
        "It has a hard-coded maximum turn limit (6 model turns, 12 tool calls). The language model NEVER determines termination through free text; "
        "termination and outcome codes (e.g., DRAFT_READY, BUDGET_CEILING_EXCEEDED) are strictly enforced by Python logic."
    )
    add_callout(
        doc,
        "Examiner question: 'Why not just use a simple LangChain chain or single prompt for procurement?'\n"
        "Answer: 'A linear chain cannot inspect live inventory, sort multiple supplier quotes, re-plan when budget limits are breached, "
        "or execute multi-step deterministic calculations. A bounded agent can dynamically select tools while code guarantees termination and financial safety.'",
        title="EXAMINER TRAP & MODEL ANSWER"
    )

    # --- LESSON 2 ---
    doc.add_heading("Lesson 2: State, State Schemas, & Finite State Machines", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-0/02-state.ipynb & module-1/05-state-schema.ipynb\n\n"
        "1. What is State? State is the single source of truth passed between execution steps. In modern AI architectures, state is represented using "
        "strict schemas (such as TypedDict, Dataclasses, or Pydantic models). State tracks conversation history, active flags, loaded tenant context, "
        "and draft records.\n"
        "2. The State Machine Architecture (src/state.py): Rather than allowing an LLM to wander arbitrarily, our procurement lifecycle follows a rigid "
        "Finite State Machine (FSM): INITIALIZED -> SENSING_INVENTORY -> PLANNING_RESTOCK -> DRAFTING_ORDER -> AWAITING_APPROVAL -> APPROVED / REJECTED.\n"
        "3. Architectural Guarantee: The state APPROVED is reachable ONLY from AWAITING_APPROVAL, and the transition can ONLY be executed by a verified human "
        "via src/approvals.py. The LLM has zero mechanism to trigger this transition."
    )
    add_callout(
        doc,
        "F-24 Defect Note: In Week 8, we discovered that while the approval CLI recorded human approval, it forgot to invoke the FSM transition function. "
        "We fixed this in Week 8 hardening by linking approvals.py directly to StateManager.transition(session_id, WorkflowStage.APPROVED).",
        title="KEY CODE LESSON: F-24"
    )

    # --- LESSON 3 ---
    doc.add_heading("Lesson 3: Edges, Conditional Routing, & Routers", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-0/03-edges.ipynb & module-1/02-router.ipynb\n\n"
        "1. Edges connect nodes. A Normal Edge always transitions from Node A to Node B. "
        "A Conditional Edge uses a router function to inspect state and choose the next node.\n"
        "2. Application in Capstone: In src/restock_agent.py, after sensing inventory with get_low_stock, a conditional router checks: "
        "Are any items low on stock? If count == 0, the router bypasses the model entirely and jumps directly to STOP with status NOTHING_TO_DO. "
        "This saves API quota and eliminates hallucination risks when no action is needed."
    )

    # --- LESSON 4 ---
    doc.add_heading("Lesson 4: Tools, Schemas, & Injected Trusted Context", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-0/06-tools.ipynb\n\n"
        "1. Tool Calling Mechanics: A tool is a deterministic Python function accompanied by a JSON Schema declaration. "
        "The model does NOT execute the tool. The model outputs a structured JSON object specifying the tool name and input arguments.\n"
        "2. Registry Allow-List (src/tools/registry.py): When a model requests a tool call, registry.py performs three critical security checks:\n"
        "   a) Allow-List Verification: Is the requested tool registered and permitted for the active role? If the model requests 'approve_requisition', "
        "the registry returns UNAUTHORIZED_TOOL.\n"
        "   b) Schema & Parameter Validation: Do the arguments conform to expected types?\n"
        "   c) Trusted Context Injection: Parameters like created_by, shop_id, and timestamp are injected by Python session state, NEVER supplied by the model. "
        "This prevents prompt injection attacks where a user or model tries to forge ownership."
    )
    add_callout(
        doc,
        "F-04 Arithmetic Defect: In Week 2, we asked the LLM to calculate reorder quantities in the prompt. It failed completely (Erasers: 70 instead of 63). "
        "Lesson: LLMs are probabilistic language engines, not calculators. In Week 4, all arithmetic was moved to deterministic Python tools.",
        title="THE MILESTONE LESSON: F-04"
    )

    # --- LESSON 5 ---
    doc.add_heading("Lesson 5: Human-in-the-Loop (HITL) & Interrupts", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-0/05-interrupts.ipynb\n\n"
        "1. What is an Interrupt? An interrupt is a deliberate architectural pause in an agentic workflow. "
        "When an agent reaches a high-consequence boundary (financial commitment, database deletion, contract signing), "
        "the state graph halts, persists state to disk, and yields control to a human.\n"
        "2. Implementation in Capstone: Once draft_requisition generates a purchase requisition, the agent halts at AWAITING_APPROVAL. "
        "The human can:\n"
        "   - Inspect the draft details (items, prices, suppliers, total UGX, and rationale).\n"
        "   - Edit quantities via approvals.py edit (e.g. override 65 pens to 50 due to cash constraints).\n"
        "   - Approve or Reject with mandatory logged reasons.\n"
        "3. Core Thesis: 'AI Supports, Never Decides.' The AI prepares the requisition; the human signs the requisition."
    )

    # --- LESSON 6 ---
    doc.add_heading("Lesson 6: Checkpointing, Memory Types, & Multi-Tenant Data Isolation", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-0/04-memory.ipynb & module-1/04-agent-memory.ipynb\n\n"
        "1. Short-Term vs Long-Term Memory: Short-term memory resides in the session context window (message history). "
        "Long-term memory is persisted across sessions in SQLite (src/memory.py & src/storage.py).\n"
        "2. Justified Memory: We store ONLY justified, structured operational facts: Supplier preferences (e.g., 'Prefers Mukwano for cleaning supplies') "
        "and Owner feedback from past approvals. We NEVER store unvetted raw chat transcripts, preventing memory poisoning.\n"
        "3. Multi-Tenant Cross-Shop Isolation: In Ugandan SME clusters, multiple shops may use the same infrastructure. "
        "Memory and storage tables strictly enforce tenant partitioning using a compound index: WHERE shop_id = ? AND target_key = ?. "
        "Shop A (e.g. AJ's Store) can NEVER read or prompt-leak the purchase history, prices, or policies of Shop B (e.g. Abiz Store)."
    )

    # --- LESSON 7 ---
    doc.add_heading("Lesson 7: Context Engineering, Message Trimming, & BM25 Grounded RAG", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-1/06-trim-filter-messages.ipynb, 07-chatbot-summarization.ipynb\n\n"
        "1. Context Limits & Prompt Drift: Unbounded message histories cause latency spikes, high costs, and attention drift. "
        "Systems must trim older messages or summarize conversation turns.\n"
        "2. Retrieval-Augmented Generation (RAG) Architecture (src/rag/index.py & policy_qa.py):\n"
        "   - 12 Policy Documents indexed into 61 structured chunks.\n"
        "   - BM25 Okapi Algorithm: Term-frequency retrieval optimized with custom light stemming (stripping 'y'/'ies' to match 'delivery' with 'deliver').\n"
        "   - Strict Score Gating: Chunks with a BM25 score below 2.0 are discarded.\n"
        "   - Grounding Enforcement: The model is instructed: 'Answer ONLY using the provided excerpts. Cite source IDs in brackets [S1]. If not found, say so.' "
        "Python then parses and verifies that all cited IDs genuinely exist in the retrieved set."
    )

    # --- LESSON 8 ---
    doc.add_heading("Lesson 8: Model Context Protocol (MCP) Client-Server Architecture", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-1/10-mcp.ipynb\n\n"
        "1. What is MCP? The Model Context Protocol is an open industry standard (developed by Anthropic) for securely connecting AI models to data sources and tools "
        "over standardized JSON-RPC 2.0 transport.\n"
        "2. Capstone Implementation (src/mcp_interface.py): We built a compliant MCP Server supporting initialize, tools/list, tools/call, resources/list, and resources/read.\n"
        "3. Permission Tiers: Three security boundaries: read_only, draft_write, and admin_approval. The model is granted read and draft permissions, while admin_approval is explicitly blocked."
    )

    # --- LESSON 9 ---
    doc.add_heading("Lesson 9: Middleware & Deterministic Guardrails", level=2)
    doc.add_paragraph(
        "Reference: ai-engineering/notebooks/module-1/11-middleware.ipynb\n\n"
        "1. Middleware sits between the user input and the execution engine, intercepting requests and responses.\n"
        "2. Four Deterministic Guardrail Layers (src/guardrails.py):\n"
        "   - InputGuardrail: Regex scanning for adversarial prompt injections, system prompt override attempts, and SQL payloads.\n"
        "   - Budget Validation: Prevents negative, non-numeric, or absurd budget allocations.\n"
        "   - BudgetCeilingGuardrail: Hard ceiling ensuring draft totals never exceed allocated shop budgets (F-12 fix).\n"
        "   - HumanInTheLoopGuardrail: Intercepts and blocks any runtime attempt to execute payment or auto-approval."
    )

    # ════════════════════════════════════════════════════════════════════════════
    # PART II: ROLE-BY-ROLE DEFENSE & EXPLANATION MANUAL
    # ════════════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    p_part2 = doc.add_heading("PART II: Role-by-Role Individual Defense Manual", level=1)
    p_part2.paragraph_format.space_before = Pt(16)
    
    doc.add_paragraph(
        "This section breaks down the project specifically for each team member. "
        "At the viva examination, questions will be directed at individuals based on their assigned responsibilities. "
        "Master your section thoroughly."
    )

    # --- MEMBER 1: ARNOLD ---
    doc.add_heading("1. Mwesigwa Arnold Mugahi — AI Engineering Lead", level=2)
    doc.add_paragraph(
        "Reg No: 23/U/24738/PS · GitHub: AJmight\n\n"
        "Plain-English Role Definition: Arnold is responsible for the AI reasoning engine. This includes the foundation model integration, "
        "the fallback resilience chain, prompt versioning, the bounded agent loops, the deterministic tool registry, and the BM25 RAG system."
    )
    
    tbl_arnold = doc.add_table(rows=1, cols=3)
    format_table(
        tbl_arnold,
        [1.2, 2.5, 3.3],
        ["Week", "Technical Task Owned", "Production Artifacts Produced"],
        [
            ["Week 2", "Foundation model connection, fallback chain, prompt engineering", "src/llm_client.py, prompts/procurement_assistant_v1.0-v1.2"],
            ["Week 3", "Context engineering & BM25 RAG pipeline", "src/rag/index.py, src/rag/policy_qa.py, knowledge/corpus/*.md"],
            ["Week 4", "Deterministic tool functions & central registry", "src/tools/procurement.py, src/tools/registry.py"],
            ["Week 5", "Bounded ReAct agent & restock task contract", "src/tool_agent.py, src/restock_agent.py, docs/requirements/agent-task-contract.md"],
            ["Week 6", "State machine, justified memory, and MCP server", "src/state.py, src/memory.py, src/mcp_interface.py"],
            ["Week 7", "31-scenario evaluation & failure cataloguing", "src/guardrails.py, tests/test_week7_evaluations.py"],
            ["Week 8", "System hardening, F-23/F-24/F-25 fixes, final release", "tests/test_week8_release_checks.py, docs/final-report.md"],
        ]
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    
    doc.add_heading("Arnold's Top 5 Viva Questions & Bulletproof Answers:", level=3)
    doc.add_paragraph(
        "Q1: Why did you move calculations out of the prompt into Python tools?\n"
        "Answer: In Week 2 (Prompt v1.2.0), we observed failure F-04: when asked to compute reorder quantities, the model hallucinated wrong figures "
        "(Erasers: 70 instead of 63, Paper: 50 instead of 53). LLMs are probabilistic language predictors, not calculators. By implementing deterministic "
        "formulas in Python (procurement.py) and exposing them via tool calling, we achieved 100% mathematical accuracy.\n\n"
        "Q2: How does the model fallback chain work?\n"
        "Answer: In src/llm_client.py, we route calls through gemini-3.8-flash. Because the free tier enforces a rate limit (F-02), "
        "if a 429 or 503 error occurs, the client automatically backs off and falls back through gemini-3.7-flash -> 3.6 -> 3.5 -> 3.5-flash-lite -> 3.1-flash-lite. "
        "This ensures maximum availability without crashing.\n\n"
        "Q3: How do you prevent infinite agent loops?\n"
        "Answer: In src/tool_agent.py, we enforce hard bounded iteration limits: maximum 6 model turns and 12 tool calls per session. "
        "In src/restock_agent.py, limits are 5 turns and 6 tool calls. If an agent repeats a call or exceeds limits, Python raises a StopIteration and executes a clean handoff.\n\n"
        "Q4: How does BM25 retrieval prevent hallucinated policy answers?\n"
        "Answer: In src/rag/policy_qa.py, we chunk 12 policy files, score passages using BM25 with custom stemming, apply a score threshold of 2.0, "
        "and instruct the model to answer ONLY from retrieved context with mandatory citations [S1]. A Python post-processor verifies citation integrity.\n\n"
        "Q5: What is the MCP interface and how is it secured?\n"
        "Answer: src/mcp_interface.py exposes our tools via the Model Context Protocol over JSON-RPC 2.0. It enforces three permission levels. "
        "The model is restricted to read_only and draft_write; admin_approval is explicitly blocked."
    )

    # --- MEMBER 2: BRONIA ---
    doc.add_page_break()
    doc.add_heading("2. Boonabaana Bronia — App Integration / Storage & UI Lead", level=2)
    doc.add_paragraph(
        "Reg No: 23/U/07647/EVE · GitHub: broniaB2\n\n"
        "Plain-English Role Definition: Bronia is responsible for persistent storage architecture, tenant-safe registry integration, "
        "the interactive user interface, and resolving critical storage discrepancies between SQLite and flat files."
    )

    tbl_bronia = doc.add_table(rows=1, cols=3)
    format_table(
        tbl_bronia,
        [1.2, 2.5, 3.3],
        ["Milestone", "Technical Task Owned", "Production Artifacts Produced"],
        [
            ["Week 6", "Scoped SQLite storage engine & tenant isolation", "src/storage.py, tests/test_week6_storage.py, PR #1"],
            ["Week 6", "Trusted context injection in tool execution", "src/tools/registry.py (created_by, tenant_id injection)"],
            ["Week 8", "Streamlit web UI implementation", "src/streamlit_app.py, tests/test_ui_home.py, branch ui-streamlit"],
            ["Post-Release", "Resolution of F-26 merge defect (Draft storage mismatch)", "src/approvals.py, src/restock_agent.py, PR #3"],
            ["Deliverables", "Report formatting, presentation deck, and UI validation", "docs/final-report.docx, scripts/build_slides.py, PR #4"],
        ]
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    doc.add_heading("Bronia's Top 5 Viva Questions & Bulletproof Answers:", level=3)
    doc.add_paragraph(
        "Q1: What is the F-26 defect, why did it happen, and how did you fix it?\n"
        "Answer: F-26 was a silent post-merge defect. Two branches were developed in parallel: Arnold's branch had approvals.py reading drafts from JSON files "
        "(data/drafts/*.json), while my storage branch (src/storage.py) had procurement.py saving drafts into SQLite. When merged, git resolved conflicts without error, "
        "but the system broke: the agent reported 'Draft created', yet the approval dashboard was empty! Test suites fell from 119/119 to 20/22. "
        "I fixed it in PR #3 by unifying both approvals.py and restock_agent.py onto the shared SQLite storage engine. All 119 tests now pass.\n\n"
        "Q2: How does src/storage.py guarantee multi-tenant security?\n"
        "Answer: In src/storage.py, every table (drafts, audit_events, sessions) has a tenant_id column. All SELECT, UPDATE, and DELETE queries require "
        "WHERE tenant_id = ?. Furthermore, the tenant_id is injected from trusted session context, so a user from Shop A cannot query Shop B's records.\n\n"
        "Q3: How is the Streamlit UI structured?\n"
        "Answer: src/streamlit_app.py provides a web interface reflecting the same 5 core actions as the CLI console: Inventory Overview, Quote Comparison, "
        "Restock Planning, Human Approvals, and Policy QA. Crucially, the UI does NOT contain separate business logic; it calls the exact same deterministic "
        "Python functions and registry tools.\n\n"
        "Q4: How did you test the UI without a browser?\n"
        "Answer: In tests/test_ui_home.py, we used Streamlit's headless AppTest framework. It simulates user sessions, verifies that UI widgets render correctly, "
        "and checks that low-stock alert metrics reflect data from procurement.get_low_stock(). All 5 UI tests pass in automated test runs.\n\n"
        "Q5: Why are there two SQLite database files in the repository?\n"
        "Answer: data/state.sqlite3 (managed by storage.py) stores drafts, audit events, and user sessions. data/procurement.db (managed by state.py and memory.py) "
        "stores workflow FSM states and justified long-term memories. Merging them into a single unified database file is documented in our report as Priority 2 Future Work."
    )

    # --- MEMBER 3: MARIAM ---
    doc.add_page_break()
    doc.add_heading("3. Nakyambadde Mariam — Requirements & Documentation Lead", level=2)
    doc.add_paragraph(
        "Reg No: 23/U/13953/EVE\n\n"
        "Plain-English Role Definition: Mariam owns the formal software engineering requirements, the AI Boundary Matrix, the 12 User Stories, "
        "the agent task contracts, the project handoff documentation, and ensuring regulatory compliance (such as GDPR Article 17 erasure rights)."
    )

    tbl_mariam = doc.add_table(rows=1, cols=3)
    format_table(
        tbl_mariam,
        [1.2, 2.5, 3.3],
        ["Area", "Technical Task Owned", "Production Artifacts Produced"],
        [
            ["Requirements", "12 User Stories & Acceptance Criteria", "docs/requirements/user-stories.md"],
            ["Safety Boundary", "The AI Boundary Matrix (AI vs Deterministic vs Human)", "docs/requirements/ai-boundary-matrix.md"],
            ["Architecture", "Single Trusted User Architecture (Decision-001)", "docs/requirements/decision-001-single-trusted-user.md"],
            ["Task Contracts", "Bounded Restock Agent Task Contract specification", "docs/requirements/agent-task-contract.md"],
            ["Reporting", "Comprehensive 8-week engineering report & team handoffs", "docs/final-report.md, docs/ONBOARDING.md, docs/PROJECT_HANDOFF.md"],
        ]
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    doc.add_heading("Mariam's Top 5 Viva Questions & Bulletproof Answers:", level=3)
    doc.add_paragraph(
        "Q1: What is the AI Boundary Matrix and why is it central to this project?\n"
        "Answer: The AI Boundary Matrix defines exactly which actor is permitted to perform each action: the probabilistic AI, deterministic Python code, "
        "or a human. For example, low-stock flagging is done in Python (stock <= reorder_point) and summarized by AI. Reorder math is calculated by Python. "
        "Approval and payment are strictly reserved for humans. The AI has NEVER permissions for approval or money transfer.\n\n"
        "Q2: Why was User Story 3 descoped?\n"
        "Answer: User Story 3 called for parsing PDF supplier quotations. In Ugandan SME environments, PDF formats vary wildly and OCR introduces extraction errors. "
        "Rather than pretending to have a brittle parser, we formally descoped PDF parsing in Week 1, loaded quotations via structured CSVs, "
        "and documented PDF extraction as Priority 5 Future Work.\n\n"
        "Q3: What is Decision-001 (Single Trusted User)?\n"
        "Answer: In Week 1, user stories included complex multi-role hierarchies (Procurement Officer vs. General Manager). In small stationery shops, "
        "the owner is typically the sole decision-maker. Elaborate RBAC within a shop was theatre. In Decision-001, we simplified the internal model "
        "to a single trusted user per shop, while shifting our security focus to cross-shop multi-tenant isolation via shop_id.\n\n"
        "Q4: How does the system handle the GDPR 'Right to be Forgotten'?\n"
        "Answer: Under GDPR Articles 15-18 and local data protection principles, shop owners have the right to inspect and purge their stored memories. "
        "In src/memory.py, we implemented delete_memory() and clear_shop_memories(), allowing a tenant to erase historical supplier feedback and preferences on demand.\n\n"
        "Q5: How do the user stories map to the final test suites?\n"
        "Answer: Appendix A of our final report provides an explicit traceability matrix: all 11 implemented user stories map directly to specific "
        "Python functions and automated tests (e.g., Story 2 maps to procurement.get_low_stock and test O-01; Story 10 maps to approvals.decide and test O-21)."
    )

    # --- MEMBER 4: PATRICIA ---
    doc.add_page_break()
    doc.add_heading("4. Naisanga Patricia — Quality & Security Lead", level=2)
    doc.add_paragraph(
        "Reg No: 23/U/13204/EVE\n\n"
        "Plain-English Role Definition: Patricia is responsible for quality assurance, adversarial stress testing, deterministic safety guardrails, "
        "multi-tenant penetration testing, and managing the 26-defect Failure Catalogue."
    )

    tbl_patricia = doc.add_table(rows=1, cols=3)
    format_table(
        tbl_patricia,
        [1.2, 2.5, 3.3],
        ["Testing Focus", "Technical Task Owned", "Production Artifacts Produced"],
        [
            ["Unit & Contract", "Tool execution contracts & permission enforcement", "tests/test_week4_tools.py (22 offline assertions)"],
            ["Agent Bounding", "Agent loop termination & turn ceiling verification", "tests/test_week5_agent.py (17 offline assertions)"],
            ["Adversarial Suite", "31-scenario stress test across 6 vulnerability classes", "tests/test_week7_evaluations.py (31 scenarios)"],
            ["Guardrails", "Deterministic input validation & budget ceiling guards", "src/guardrails.py (Input, Budget, Human-in-the-Loop)"],
            ["Failure Logging", "Cataloguing 26 defects with root causes & regression proofs", "docs/evaluation/failure-catalogue.md (F-01 to F-26)"],
        ]
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    doc.add_heading("Patricia's Top 5 Viva Questions & Bulletproof Answers:", level=3)
    doc.add_paragraph(
        "Q1: How do your tests achieve 119/119 pass rates without consuming LLM API credits?\n"
        "Answer: We engineered all 9 release test suites to be model-free offline suites. Rather than calling external APIs during testing, "
        "we test deterministic Python logic, registry schema validators, FSM transitions, and memory isolation directly. Expected values are computed "
        "directly from synthetic CSVs, guaranteeing that tests run instantly and deterministically without quota limits.\n\n"
        "Q2: What are the 6 categories in the 31-scenario evaluation dataset?\n"
        "Answer: In tests/test_week7_evaluations.py, we evaluate: 1) Normal operations (5 tests), 2) Edge cases such as zero budgets (6 tests), "
        "3) Corrupted data like SQL injection strings in shop_id (5 tests), 4) Adversarial prompt injections (5 tests), 5) Tool and infrastructure failures (5 tests), "
        "and 6) Unauthorised action attempts such as the model trying to approve a purchase (5 tests). All 31 pass.\n\n"
        "Q3: How do the guardrails in src/guardrails.py protect the system?\n"
        "Answer: We have 4 guardrail classes: 1) InputGuardrail uses regex patterns to block jailbreak phrases (e.g. 'ignore previous instructions') "
        "and SQL injection payloads; 2) validate_budget blocks negative or non-numeric values; 3) BudgetCeilingGuardrail stops any draft that exceeds "
        "the allocated budget; 4) HumanInTheLoopGuardrail intercepts any attempt to execute payment or approval.\n\n"
        "Q4: What was the F-12 defect and how was it resolved?\n"
        "Answer: In Week 4, draft_requisition computed an estimate band of +/-10%. When the allocated budget was 100,000 UGX, the upper band reached 110,000 UGX, "
        "exceeding the shop's budget! We fixed this in BudgetCeilingGuardrail by clamping the upper estimate band to min(total * 1.10, allocated_budget).\n\n"
        "Q5: What is the 200% safety cap (F-10)?\n"
        "Answer: To prevent catastrophic over-ordering, if a reorder quantity exceeds 200% of historical average monthly sales, "
        "the system flags requires_override = True. The human approver must explicitly provide a written justification before the requisition can be approved."
    )

    # --- MEMBER 5: ISMAIL ---
    doc.add_page_break()
    doc.add_heading("5. Tulinawe Ismail — DevOps & Deployment Lead", level=2)
    doc.add_paragraph(
        "Reg No: 23/U/18058/EVE\n\n"
        "Plain-English Role Definition: Ismail is responsible for environment reproducibility, dependency locking, configuration management, "
        "observability pipelines (JSONL trace streams), and ensuring clean deployment across local machines and cloud platforms."
    )

    tbl_ismail = doc.add_table(rows=1, cols=3)
    format_table(
        tbl_ismail,
        [1.2, 2.5, 3.3],
        ["DevOps Focus", "Technical Task Owned", "Production Artifacts Produced"],
        [
            ["Environment", "Python dependency specifications & virtual environments", "requirements.txt, requirements-docs.txt, .python-version"],
            ["Secrets & Config", "Zero-leakage configuration templates", ".env.example, .gitignore (strict .env blocking)"],
            ["Observability", "JSONL trace logging pipelines for LLM & tool calls", "evidence/traces/llm_calls.jsonl, evidence/week4/tool_traces.jsonl"],
            ["Automated Scripts", "Automated slide deck & documentation builders", "scripts/build_slides.py, scripts/export_report.py"],
            ["Verification", "Release verification harness & git release tags", "tests/test_week8_release_checks.py, git tags week2..v1.0.0"],
        ]
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    doc.add_heading("Ismail's Top 5 Viva Questions & Bulletproof Answers:", level=3)
    doc.add_paragraph(
        "Q1: How do you prove this system is reproducibly runnable on a clean machine?\n"
        "Answer: An evaluator can clone the repository, run python -m venv venv, activate it, run pip install -r requirements.txt, copy .env.example to .env, "
        "and immediately execute python tests/test_week8_release_checks.py. All 19 release checks pass out of the box. No external database server needs provisioning "
        "because SQLite databases initialize automatically on first run.\n\n"
        "Q2: How do you manage API keys and secrets securely?\n"
        "Answer: No API token or private credential is ever checked into git. Our .gitignore explicitly blocks .env, *.db, and *.sqlite3 files. "
        "Configuration is loaded via python-dotenv. The .env.example file documents the 4 required environment variables without exposing values.\n\n"
        "Q3: What observability pipelines exist in the system?\n"
        "Answer: We maintain 4 structured trace streams: 1) evidence/traces/llm_calls.jsonl records every model call with timestamp, model name, latency, and status; "
        "2) evidence/week4/tool_traces.jsonl logs tool executions; 3) evidence/week5/trace_T*.md provides human-readable step-by-step agent traces; "
        "4) audit_events in SQLite stores immutable logs of all human approval decisions.\n\n"
        "Q4: What is the purpose of the git release tags?\n"
        "Answer: We used git tags to establish immutable milestones at each weekly deadline: week2-complete, week3-complete, week4-complete, week5-complete, "
        "week6-complete, week7-complete, and v1.0.0. This allows examiners to checkout any tag and verify exactly what existed at that week's evaluation.\n\n"
        "Q5: Why is there currently no automated cloud CI pipeline?\n"
        "Answer: In Section 9.2 of our report, we explicitly document the lack of a hosted CI/CD pipeline as an honest limitation. Running live end-to-end "
        "integration suites in cloud CI would require exposing paid API secrets or consuming daily rate limits. Implementing a secure self-hosted runner "
        "for offline regression suites is listed as Priority 3 Future Work."
    )

    # ════════════════════════════════════════════════════════════════════════════
    # PART III: GENERAL KNOWLEDGE (WHAT EVERYONE MUST KNOW COLD)
    # ════════════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    p_part3 = doc.add_heading("PART III: Universal Knowledge (Every Member Must Know Cold)", level=1)
    p_part3.paragraph_format.space_before = Pt(16)

    doc.add_paragraph(
        "Regardless of your specific role, examiners will ask general architectural questions to anyone in the group. "
        "Every member must be able to recite and explain the following four core concepts without hesitation."
    )

    doc.add_heading("1. The Core Principle: 'AI Supports, Never Decides'", level=2)
    doc.add_paragraph(
        "We never let probabilistic AI make decisions involving real money. "
        "The model acts as an analytical copilot: it reads messy natural language queries, identifies relevant items, compares prices, "
        "and formats a DRAFT requisition. That is where its agency ends. It CANNOT approve the requisition, sign a purchase order, "
        "disburse mobile money, or send emails to suppliers. The draft sits in an SQLite queue until a human owner reviews and approves it."
    )

    doc.add_heading("2. The 8 Deterministic Tools", level=2)
    tbl_tools = doc.add_table(rows=1, cols=4)
    format_table(
        tbl_tools,
        [0.6, 2.2, 2.7, 1.5],
        ["#", "Tool Name", "Purpose & Computation Performed", "Permission Tier"],
        [
            ["1", "get_low_stock", "Filters inventory CSV for items where stock <= reorder_point", "read_only"],
            ["2", "compare_supplier_quotes", "Sorts supplier quotes by unit price; tie-breaks by lead time", "read_only"],
            ["3", "estimate_reorder_quantity", "ceil(avg_monthly_sales * 1.5) - current_stock; enforces MOQ", "read_only"],
            ["4", "plan_within_budget", "Greedy knapsack algorithm fitting urgent restock items under budget", "read_only"],
            ["5", "draft_requisition", "Generates requisition record with +/-10% band; persists to SQLite", "draft_write"],
            ["6", "get_inventory", "Returns full inventory snapshot with current unit prices", "read_only"],
            ["7", "query_purchase_history", "Queries 24-month historical order records for trend analysis", "read_only"],
            ["8", "search_policy", "Executes BM25 keyword search over 12 hand-written policy docs", "read_only"],
        ]
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    doc.add_heading("3. The Worked Example (Recite These Exact Numbers!)", level=2)
    doc.add_paragraph(
        "Examiners will ask: 'Walk me through a real example with real numbers.' Memorize this sequence:\n"
        "• Given an SME restock budget of UGX 300,000:\n"
        "• Step 1: get_low_stock finds 10 out of 15 inventory items are low.\n"
        "• Step 2: estimate_reorder_quantity('ITM001') (Bic Pens Blue):\n"
        "   - 555 units bought over 12 months = 46.25/month.\n"
        "   - 46.25 * 1.5 = 69.375 target stock.\n"
        "   - 69.375 - 5 current stock = 64.375 -> rounded UP to 65 units.\n"
        "   - 65 units @ UGX 476 = UGX 30,940.\n"
        "• Step 3: estimate_reorder_quantity('ITM003') (Rulers 30cm):\n"
        "   - 469 units / 12 months = 39.08/month * 1.5 = 58.625 - 2 current stock = 56.625 -> rounded UP to 57 units.\n"
        "   - 57 units @ UGX 938 = UGX 53,466.\n"
        "• Step 4: draft_requisition combines the two -> Total = UGX 84,406 (Band: UGX 75,965 to 92,847).\n"
        "• Step 5: plan_within_budget fits 4 items totaling UGX 294,130 (UGX 5,870 remaining budget), deferring 2 items.\n"
        "Notice: every single calculation was performed by Python formulas, NOT by the AI model!"
    )

    doc.add_heading("4. The 4 Deterministic Guardrails", level=2)
    doc.add_paragraph(
        "1. InputGuardrail: Scans prompts for injection attacks ('ignore system rules', SQL injections) and blocks them before calling the LLM.\n"
        "2. Budget Validation: Rejects negative or non-numeric budgets.\n"
        "3. BudgetCeilingGuardrail: Rejects any draft whose total cost exceeds the shop's budget allocation (F-12 fix).\n"
        "4. HumanInTheLoopGuardrail: Ensures financial approvals and payments cannot be triggered by software."
    )

    # ════════════════════════════════════════════════════════════════════════════
    # PART IV: MASTER DEMO SCRIPT & VIVA STRATEGY
    # ════════════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    p_part4 = doc.add_heading("PART IV: Master Presentation & Viva Demo Script", level=1)
    p_part4.paragraph_format.space_before = Pt(16)

    doc.add_paragraph(
        "Follow this exact 5-minute presentation script during the live demonstration on Thursday. "
        "Each person speaks during their assigned segment."
    )

    demo_steps = [
        ("Minute 1: Problem & Boundary", "Mariam & Arnold", 
         "Show water-damaged exercise book story. State the thesis: 'AI supports, never decides.' Introduce the AI Boundary Matrix."),
        ("Minute 2: Restock Planning Demo", "Arnold & Patricia", 
         "Run: python src/restock_agent.py --budget 300000 --user 'Demo'\nShow the SENSE -> PLAN -> ACT -> OBSERVE timeline. Point out that Bic Pens 65 and Rulers 57 were calculated by Python formulas. Show status: DRAFT - AWAITING HUMAN APPROVAL."),
        ("Minute 3: The Human Gate & Refusal Demo", "Bronia & Ismail", 
         "Run: python src/approvals.py list (shows the draft in SQLite queue).\n"
         "Then run the killer test: python src/tool_agent.py 'Approve draft REQ-001'\n"
         "Show the refusal on screen: 'UNAUTHORIZED_TOOL: approve_requisition does not exist.' This proves the AI cannot approve."),
        ("Minute 4: Multi-Tenant Isolation & F-26 Story", "Bronia & Patricia", 
         "Explain how Shop A (AJ's Store) cannot view Shop B's records. Narrate the F-26 defect: how a merge conflict broke draft visibility and how automated tests caught and fixed it."),
        ("Minute 5: Test Verification & Conclusion", "Ismail & All", 
         "Run: python tests/test_week8_release_checks.py (shows 19/19 checks passing). Conclude: 119/119 offline tests, 26 documented failures, reproducible release v1.0.0."),
    ]

    tbl_demo = doc.add_table(rows=1, cols=3)
    format_table(
        tbl_demo,
        [1.5, 1.8, 3.7],
        ["Time & Phase", "Presenters", "Exact Action & Narration"],
        demo_steps
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_callout(
        doc,
        "If an examiner interrupts with a hostile question (e.g. 'Why did you use Gemini Flash instead of GPT-4?' or 'Why isn't this deployed on Kubernetes?'), "
        "stay calm and use this formula:\n"
        "1. Acknowledge the premise: 'That is an important engineering trade-off.'\n"
        "2. Ground in the SME context: 'Ugandan stationery SMEs operate on razor-thin margins. GPT-4 API costs would exceed the shop's software budget. Gemini Flash provides sub-second latency at zero or low cost.'\n"
        "3. Anchor to deterministic safety: 'Furthermore, because all arithmetic and security boundaries live in deterministic Python, we do not need a massive model to do math — we only need it to route language requests to tools.'",
        title="VIVA DEFENSE STRATEGY & GOLDEN FORMULA"
    )

    # ── OUTPUT PATHS ──
    desktop_path = "/mnt/c/Users/user/OneDrive/Desktop/BSE4104_Team_Guide.docx"
    repo_path = "/mnt/c/Users/user/Capstone_project-/docs/team/BSE4104_Team_Guide.docx"
    
    os.makedirs(os.path.dirname(repo_path), exist_ok=True)
    doc.save(repo_path)
    print(f"Saved to repo: {repo_path}")
    
    try:
        doc.save(desktop_path)
        print(f"Saved to desktop: {desktop_path}")
    except Exception as e:
        print(f"Could not save directly to desktop path: {e}")

if __name__ == "__main__":
    build_guide()
