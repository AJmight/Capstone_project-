"""Build the Week 8 final evidence pack (run from the repository root).

WHAT THIS SCRIPT IS FOR
    The capstone is graded on evidence, not on promises. A reviewer must be able to
    see, without trusting our word, that every offline suite passed on the release
    commit. This script re-runs all seven offline suites, captures their *verbatim*
    output into `evidence/final/regression_run_2026-10-20.md`, and copies a small
    sample of the raw trace files (tool calls, LLM calls, agent runs, RAG traces)
    into `evidence/final/traces/` so the pack is self-contained.

WHY IT IS OFFLINE BY DESIGN
    Every suite it runs is offline: no model call, no network, no API quota. The
    Gemini free tier allows only 20 requests per model per day, so a release check
    that consumed quota would be unrunnable on the demo laptop. The script is
    therefore safe to run any time, including minutes before a presentation.

HOW TO RUN IT
    py scripts\build_evidence_final.py
    (It re-runs the suites itself; the markdown it writes is the record of that run.)
"""

import os
import subprocess
import sys
from pathlib import Path

# The repository root is the parent of `scripts/` (this file lives in scripts/).
ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / "evidence" / "final"
TRACES = FINAL / "traces"
FINAL.mkdir(parents=True, exist_ok=True)
TRACES.mkdir(parents=True, exist_ok=True)
# Prefer the project virtual environment (Windows layout) so the run matches the
# versions in requirements.txt; fall back to the interpreter that started us.
PY = str(ROOT / "venv" / "Scripts" / "python.exe")
if not os.path.exists(PY):
    PY = sys.executable

# The seven offline suites that make up the release regression, in report order.
# `extra` holds the command-line flags each suite needs (some take --offline).
SUITES = [
    ("test_week3_rag.py", ["--offline"], "retrieval quality (no model call)"),
    ("test_week4_tools.py", ["--offline"], "tool contracts, permissions, failure modes"),
    ("test_week5_agent.py", ["--offline"], "bounded agent, post-conditions, hand-offs"),
    ("test_mvp_tools.py", ["--offline"], "MVP console behaviours"),
    ("test_week6_state_memory.py", [], "FSM, memory isolation, erasure, MCP"),
    ("test_week7_evaluations.py", [], "31 evaluation scenarios"),
    ("test_week8_release_checks.py", [], "release regressions found in Week 8"),
]

parts = [
    "# Final regression run — 20 October 2026 (Week 8 release check)",
    "",
    "Command: `py tests\\<suite>.py --offline` from the repository root.",
    "Python 3.13.5, Windows PowerShell, repository at commit `Week 8 hardening`.",
    "",
    "**Every suite is offline**: no model call, no network, no API quota. The release",
    "can therefore be verified on a laptop with no Gemini quota left, which matters when",
    "the free tier allows 20 requests per model per day.",
    "",
    "| Suite | Command | Result |",
    "|:---|:---|:---|",
]
for name, extra, purpose in SUITES:
    cmd = [PY, str(ROOT / "tests" / name)] + extra
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    out = (proc.stdout or "") + (proc.stderr or "")
    summary = ""
    # Parse the one-line result each suite prints. Three shapes exist:
    #   * the hand-written offline runners print "Offline: 22/22 passed"
    #   * the unittest runners print "Ran 9 tests in 0.4s" followed by "OK"
    #   * the RAG runner prints "hit@3 10/10 | context hit 10/10 | MRR 0.88"
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Offline:") and "passed" in line:
            summary = line.split("Offline:")[-1].strip()
        elif line.startswith("Ran ") and "tests in" in line:
            # "Ran 9 tests in 0.489s" -> count, then look for the OK/FAILED verdict.
            count = line.split()[1]
            verdict = next((ln.strip() for ln in lines[i:i + 4] if ln.strip() in ("OK", "FAILED")), "")
            summary = f"{count}/{count} passed" if verdict == "OK" else f"{count} tests, {verdict or 'see output'}"
        elif line.startswith("hit@3"):
            summary = line.strip()
    parts.append(f"| `{name}` | `py tests\\{name}{' ' + ' '.join(extra) if extra else ''}` | **{summary.replace('|', '/')}** |")
    parts.append("")
    parts.append(f"<details><summary>{purpose} — verbatim output</summary>")
    parts.append("")
    parts.append("```")
    parts.append(out.strip())
    parts.append("```")
    parts.append("")
    parts.append("</details>")
    parts.append("")

(FINAL / "regression_run_2026-10-20.md").write_text("\n".join(parts), encoding="utf-8")


def tail_lines(src: Path, n: int, dest: Path) -> int:
    if not src.exists():
        return 0
    lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    dest.write_text("\n".join(lines[-n:]) + "\n", encoding="utf-8")
    return len(lines)


counts = {
    "tool_traces_sample.jsonl": tail_lines(ROOT / "evidence" / "week4" / "tool_traces.jsonl", 10,
                                            TRACES / "tool_traces_sample.jsonl"),
    "llm_calls_sample.jsonl": tail_lines(ROOT / "evidence" / "traces" / "llm_calls.jsonl", 10,
                                         TRACES / "llm_calls_sample.jsonl"),
    "agent_traces_sample.jsonl": tail_lines(ROOT / "evidence" / "week5" / "restock_runs.jsonl", 3,
                                            TRACES / "agent_traces_sample.jsonl"),
    "rag_traces_sample.jsonl": tail_lines(ROOT / "evidence" / "week3" / "rag_traces.jsonl", 10,
                                          TRACES / "rag_traces_sample.jsonl"),
}

# Git history and tags as the release evidence.
hist = subprocess.run(["git", "log", "--oneline", "--all", "--graph", "--decorate"],
                      capture_output=True, text=True, cwd=str(ROOT)).stdout
(FINAL / "git_history.txt").write_text(hist, encoding="utf-8")
tags = subprocess.run(["git", "tag", "-l", "--sort=creatordate"], capture_output=True, text=True,
                      cwd=str(ROOT)).stdout
(FINAL / "git_tags.txt").write_text(tags, encoding="utf-8")

print("evidence/final written")
for k, v in counts.items():
    print(f"  {k}: {v} source lines sampled")
print("  git history lines:", len(hist.splitlines()))
print("  tags:", tags.split())
