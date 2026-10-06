"""
Tool registry and safe executor (Week 4).
=========================================

WHAT THIS FILE IS
-----------------
The "gatekeeper" between the AI model and the Python tools. When the model
says "call estimate_reorder_quantity with item=ITM001", it does NOT run the
function directly. src/tool_agent.py hands the request to execute_tool()
below, which runs these checks IN ORDER:

  1. ALLOW-LIST     Is the tool name in TOOL_REGISTRY?      no -> UNAUTHORIZED_TOOL
  2. PERMISSION     Does the user's role allow this tool?    no -> UNAUTHORIZED
  3. PARAMETERS     Are the arguments exactly what the schema says?
                    missing -> MISSING_PARAMETER, wrong/extra -> INVALID_PARAMETER
  4. CONTEXT        Values the model must never choose (who the user is) are
                    added here from the session, never from the model.
  5. RUN SAFELY     Any crash inside the tool -> TOOL_ERROR;
                    a non-dictionary result  -> UNEXPECTED_RESPONSE
  6. TRACE          Every call (allowed or blocked) is appended to
                    evidence/week4/tool_traces.jsonl

FAULT INJECTION (testing only, Week 5)
--------------------------------------
To record a genuine failure/recovery trace we can make the first N calls of a tool
fail with "SERVICE_UNAVAILABLE" (as if a data service timed out):
    registry.inject_fault("plan_within_budget", times=1)     # from a test script, or
    set AGENT_FAULTS=plan_within_budget:1                     # environment variable
It is OFF unless one of those is used, and every injected failure is marked
"injected": true in the trace so evidence is never misleading.

ROLES (who may do what)
-----------------------
  viewer  read-only tools                    (e.g. a junior staff member checking stock)
  staff   read tools + draft_requisition     (default for the shop assistant)
  owner   read tools + draft_requisition     (owner APPROVES outside the AI, in approvals.py)
Nobody - not even "owner" - gets an approve/order/pay tool, because none exists.

The model is also only SHOWN the tools its role may use (tool_declarations_for),
so a viewer's model does not even know draft_requisition exists. The permission
check in step 2 is a second, independent safety net (defence in depth).

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.2.0 (MVP: get_inventory, query_purchase_history, search_policy; maximum check)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import json                                   # write trace lines
import os                                     # read the optional AGENT_FAULTS test setting
import time                                   # measure how long each tool takes
from datetime import datetime, timezone       # trace timestamps
from pathlib import Path                      # trace file path

from tools import knowledge, procurement      # deterministic tool functions (CSV tools + policy search)

TRACE_PATH = Path("evidence/week4/tool_traces.jsonl")

# ---------------------------------------------------------------------------
# Tool declarations: what the MODEL sees (name, description, JSON Schema of arguments).
# Gemini reads these to decide which tool to call and what arguments to send.
# The same schemas are used below to validate the arguments the model sends back.
# ---------------------------------------------------------------------------
_ITEM_PARAM = {
    "type": "string",
    "description": "An item ID such as ITM001, or the item's name such as 'Bic Pens (Blue)'.",
}

TOOL_REGISTRY = {
    "get_low_stock": {
        "function": procurement.get_low_stock,
        "permission": "read",
        "declaration": {
            "name": "get_low_stock",
            "description": ("List every inventory item whose current_stock is at or below its "
                            "reorder_point, with item IDs. Use it to answer 'what is low?' and "
                            "to find item IDs before drafting."),
            "parameters_json_schema": {"type": "object", "properties": {}, "required": []},
        },
    },
    "compare_supplier_quotes": {
        "function": procurement.compare_supplier_quotes,
        "permission": "read",
        "declaration": {
            "name": "compare_supplier_quotes",
            "description": ("Return all supplier quotes for ONE item sorted cheapest first "
                            "(ties broken by shorter lead time), with minimum order quantities."),
            "parameters_json_schema": {"type": "object", "properties": {"item": _ITEM_PARAM},
                                       "required": ["item"]},
        },
    },
    "estimate_reorder_quantity": {
        "function": procurement.estimate_reorder_quantity,
        "permission": "read",
        "declaration": {
            "name": "estimate_reorder_quantity",
            "description": ("Compute the exact recommended reorder quantity for ONE item from its "
                            "purchase history (1.5 months of average demand minus current stock, "
                            "rounded up, raised to supplier minimum order), with the working and the "
                            "200% safety-cap check. Always use this instead of doing arithmetic."),
            "parameters_json_schema": {"type": "object", "properties": {"item": _ITEM_PARAM},
                                       "required": ["item"]},
        },
    },
    "draft_requisition": {
        "function": procurement.draft_requisition,
        "permission": "draft",
        "context_args": ["created_by"],       # filled from the session in step 4, never by the model
        "declaration": {
            "name": "draft_requisition",
            "description": ("Create and save a DRAFT purchase requisition for the listed items. "
                            "Python computes every quantity, price, total and budget. Items that "
                            "are not low on stock are skipped automatically. The draft is NOT sent "
                            "or approved; a human must review it."),
            "parameters_json_schema": {
                "type": "object",
                "properties": {"items": {"type": "array", "items": _ITEM_PARAM, "minItems": 1,
                                         "maxItems": procurement.MAX_ITEMS_PER_DRAFT,
                                         "description": "Items the user asked for (IDs or names)."}},
                "required": ["items"],
            },
        },
    },
    "plan_within_budget": {
        "function": procurement.plan_within_budget,
        "permission": "read",                 # read-only: it plans, it writes nothing
        "declaration": {
            "name": "plan_within_budget",
            "description": ("Decide which low-stock items fit a budget, most urgent first "
                            "(stock / reorder point). Returns 'included' items to draft, 'deferred' "
                            "items that do not fit, and 'needs_human' items that cannot be costed "
                            "(no purchase history or no quote). Writes nothing."),
            "parameters_json_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": _ITEM_PARAM, "minItems": 1, "maxItems": 50,
                              "description": "Items to consider, normally every low item ID."},
                    "budget_ugx": {"type": "integer", "minimum": 1,
                                   "description": "Spending limit in UGX. Omit if the user gave no budget."},
                },
                "required": ["items"],
            },
        },
    },
}

# --- MVP / Week 3 read-only tools -------------------------------------------
TOOL_REGISTRY["get_inventory"] = {
    "function": procurement.get_inventory,
    "permission": "read",
    "declaration": {
        "name": "get_inventory",
        "description": ("List inventory items with current stock, reorder point and whether each is low. "
                        "Optionally filter by category (Stationery, Office, Electronics)."),
        "parameters_json_schema": {"type": "object", "properties": {
            "category": {"type": "string", "description": "Optional category name; omit for all items."}},
            "required": []},
    },
}
TOOL_REGISTRY["query_purchase_history"] = {
    "function": procurement.query_purchase_history,
    "permission": "read",
    "declaration": {
        "name": "query_purchase_history",
        "description": ("Past purchases of ONE item with exact totals (quantity and spend), optionally for a "
                        "month range. Use for questions like 'how many pens did we buy in March 2025?'. "
                        "Returns data_range so you can tell the user when a period has no data."),
        "parameters_json_schema": {"type": "object", "properties": {
            "item": _ITEM_PARAM,
            "start_month": {"type": "string", "description": "First month, YYYY-MM (optional)."},
            "end_month": {"type": "string", "description": "Last month, YYYY-MM (optional)."}},
            "required": ["item"]},
    },
}
TOOL_REGISTRY["search_policy"] = {
    "function": knowledge.search_policy,
    "permission": "read",
    "declaration": {
        "name": "search_policy",
        "description": ("Search the shop's policy and procedure documents (approval limits, payments, "
                        "supplier delivery/returns/terms, reorder guidelines, supplier pressure). Returns "
                        "passages with source_id. Use it for ANY policy or process question and cite the "
                        "source_id; never answer policy questions from memory."),
        "parameters_json_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The question or key words."},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 5,
                      "description": "How many passages (default 3)."}},
            "required": ["query"]},
    },
}

# Error codes worth ONE retry of the same call (a temporary problem, not a wrong request).
RETRYABLE_ERRORS = ("SERVICE_UNAVAILABLE",)

# Fault injection state: {tool_name: number of upcoming calls that should fail}.
_FAULTS: dict[str, int] = {}


def inject_fault(tool: str, times: int = 1) -> None:
    """TESTING ONLY: make the next `times` calls of `tool` fail with SERVICE_UNAVAILABLE."""
    _FAULTS[tool] = times


def clear_faults() -> None:
    _FAULTS.clear()


def _load_env_faults() -> None:
    """Read AGENT_FAULTS like 'plan_within_budget:1,draft_requisition:2' once, if set."""
    for part in filter(None, os.getenv("AGENT_FAULTS", "").split(",")):
        name, _, times = part.partition(":")
        _FAULTS.setdefault(name.strip(), int(times or 1))


_load_env_faults()

# Which permissions each role has. A role not listed here has no permissions at all.
ROLE_PERMISSIONS = {
    "viewer": {"read"},
    "staff": {"read", "draft"},
    "owner": {"read", "draft"},
}

# JSON Schema type names -> the Python types we accept for them.
_PY_TYPES = {"string": str, "array": list, "object": dict, "integer": int, "boolean": bool}


# ---------------------------------------------------------------------------
# What the model is allowed to see
# ---------------------------------------------------------------------------
def tool_declarations_for(role: str) -> list[dict]:
    """Declarations of only the tools this role may use (least privilege)."""
    allowed = ROLE_PERMISSIONS.get(role, set())
    return [spec["declaration"] for spec in TOOL_REGISTRY.values() if spec["permission"] in allowed]


# ---------------------------------------------------------------------------
# Argument validation (step 3)
# ---------------------------------------------------------------------------
def _validate_args(name: str, args: dict, schema: dict) -> str | None:
    """
    Check the model's arguments against the tool's JSON Schema.
    Returns an error string, or None if the arguments are fine.
    (A small hand-written validator: enough for our simple schemas, no extra library.)
    """
    properties = schema.get("properties", {})
    # Gemini sends JSON numbers as floats (300000 arrives as 300000.0). Accept a float for an
    # "integer" field only if it is a whole number, and convert it, so tools always get an int.
    for key, spec in properties.items():
        value = args.get(key)
        if spec.get("type") == "integer" and isinstance(value, float) and value.is_integer():
            args[key] = int(value)
    for required in schema.get("required", []):
        if required not in args:
            return f"MISSING_PARAMETER: {name} needs '{required}'"
    for key, value in args.items():
        if key not in properties:
            return f"INVALID_PARAMETER: {name} does not accept '{key}'"
        spec = properties[key]
        expected = _PY_TYPES.get(spec.get("type"))
        if expected and not isinstance(value, expected):
            return f"INVALID_PARAMETER: '{key}' must be {spec['type']}, got {type(value).__name__}"
        if spec.get("type") == "array":
            if len(value) < spec.get("minItems", 0):
                return f"INVALID_PARAMETER: '{key}' needs at least {spec['minItems']} entry"
            if len(value) > spec.get("maxItems", len(value)):
                return f"INVALID_PARAMETER: '{key}' allows at most {spec['maxItems']} entries"
            item_type = _PY_TYPES.get(spec.get("items", {}).get("type"))
            if item_type and not all(isinstance(v, item_type) for v in value):
                return f"INVALID_PARAMETER: every entry of '{key}' must be {spec['items']['type']}"
        if spec.get("type") == "string" and not value.strip():
            return f"INVALID_PARAMETER: '{key}' must not be empty"
        if spec.get("type") == "integer":
            if isinstance(value, bool):          # True/False are ints in Python: reject them
                return f"INVALID_PARAMETER: '{key}' must be integer, got bool"
            if value < spec.get("minimum", value):
                return f"INVALID_PARAMETER: '{key}' must be at least {spec['minimum']}"
            if value > spec.get("maximum", value):
                return f"INVALID_PARAMETER: '{key}' must be at most {spec['maximum']}"
    return None


# ---------------------------------------------------------------------------
# Trace (step 6)
# ---------------------------------------------------------------------------
def _trace(record: dict) -> None:
    """Append one JSON line per tool call. Logging problems never stop the agent."""
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        print(f"[WARN] Could not write tool trace: {e}")


class _InjectedFault(Exception):
    """Raised only by fault injection; turned into a SERVICE_UNAVAILABLE result."""


# ---------------------------------------------------------------------------
# The executor: the ONLY way the agent runs a tool
# ---------------------------------------------------------------------------
def execute_tool(name: str, args: dict | None, role: str, context: dict | None = None,
                 run_id: str = "") -> tuple[dict, str]:
    """
    Run one tool request from the model, safely.

    name    tool name the model asked for
    args    arguments the model sent (may be None)
    role    the session user's role: viewer | staff | owner
    context trusted values from the session, e.g. {"created_by": "Arnold"}
    run_id  agent run ID, written to the trace so calls can be grouped

    Returns (result_dict, status) where status is one of
      ok | tool_error | blocked | invalid | crashed
    The result_dict is what gets sent back to the model.
    """
    args = dict(args or {})               # the SDK may give None or a special mapping type
    context = context or {}
    started = time.monotonic()

    spec = TOOL_REGISTRY.get(name)
    if spec is None:                                                       # step 1
        result, status = {"error": f"UNAUTHORIZED_TOOL: '{name}' is not on the allow-list"}, "blocked"
    elif spec["permission"] not in ROLE_PERMISSIONS.get(role, set()):     # step 2
        result, status = {"error": f"UNAUTHORIZED: role '{role}' may not use {name}"}, "blocked"
    else:
        problem = _validate_args(name, args, spec["declaration"]["parameters_json_schema"])  # step 3
        if problem:
            result, status = {"error": problem}, "invalid"
        else:
            # Step 4: add trusted context values (e.g. created_by) that the model never controls.
            trusted = {k: context[k] for k in spec.get("context_args", []) if k in context}
            try:                                                           # step 5
                if _FAULTS.get(name, 0) > 0:
                    # TESTING ONLY: simulate a temporary outage (see module docstring).
                    _FAULTS[name] -= 1
                    raise _InjectedFault()
                result = spec["function"](**args, **trusted)
                if not isinstance(result, dict):
                    result, status = {"error": f"UNEXPECTED_RESPONSE: {name} returned "
                                               f"{type(result).__name__}, not a dict"}, "crashed"
                else:
                    status = "tool_error" if "error" in result else "ok"
            except _InjectedFault:
                result = {"error": "SERVICE_UNAVAILABLE: the data service timed out; retry this "
                                   "call once", "injected": True}
                status = "tool_error"
            except Exception as e:                                         # a bug inside the tool
                result, status = {"error": f"TOOL_ERROR: {type(e).__name__}: {e}"}, "crashed"

    _trace({                                                               # step 6
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "tool": name,
        "role": role,
        "args": args,
        "status": status,
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
        "result": result,
    })
    return result, status
