"""
src/guardrails.py
=============================================================================
Safety Guardrails and Boundary Verification (Week 7 Deliverable)
=============================================================================

ACADEMIC CONTEXT:
  BSE4104 Emerging Trends in Software Engineering (Makerere University)
  Capstone Project: SME Procurement Preparation Agent
  Author: Mwesigwa Arnold Mugahi (Reg No: 23/U/24738/PS, GitHub: AJmight)

PURPOSE:
  Foundation models are probabilistic and susceptible to adversarial inputs,
  jailbreaks, hallucinated parameters, and silent overreach.
  In this capstone, safety and bounded agency are enforced through
  DETERMINISTIC GUARDRAILS outside the model.

KEY GUARDRAILS IMPLEMENTED:
  1. INPUT GUARDRAIL:
     - Prompt injection detection (detects commands attempting to override
       instructions, claim autonomous authority, or leak cross-shop data).
     - Shop ID sanitization: validates format to block path traversal or SQL injection.
  2. TOOL CALL GUARDRAIL:
     - Allow-list enforcement: model can ONLY call approved procurement tools.
     - Parameter boundary checks: quantities and budgets must be non-negative integers.
  3. FINANCIAL & BUDGET CEILING GUARDRAIL (Fix for F-12):
     - Validates that recommended requisition total NEVER exceeds the hard budget.
     - Rejects any draft whose cost exceeds allocated funds (strictly prevents over-ordering).
  4. HUMAN-IN-THE-LOOP (HITL) APPROVAL GATE:
     - Blocks any automated attempt to approve, pay, or execute orders.
     - Confirms that approval state can ONLY transition via explicit human signature in approvals.py.

KEY DATA FLOWS:
  - INPUT: User prompt, budget numbers, and tool call requests.
  - VALIDATION: Intercepts requests before LLM invocation or before tool execution.
  - OUTPUT: Passes validated inputs through, or raises GuardrailViolation with explanatory trace.
=============================================================================
"""

import re
from typing import Any, Dict, List, Optional, Tuple


class GuardrailViolation(Exception):
    """Raised when a request violates safety, security, or financial guardrails."""
    def __init__(self, code: str, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.context = context or {}


class InputGuardrail:
    """
    Sanitizes and validates incoming user prompts and task parameters.
    Blocks prompt injections and malicious parameter spoofing.
    """

    # Adversarial patterns commonly seen in prompt injection attempts
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all)\s+instructions",
        r"you\s+are\s+now\s+(an?\s+)?unrestricted",
        r"system\s*:\s*override",
        r"auto[- ]?approve\s+(this\s+)?(order|requisition|draft)",
        r"bypass\s+(human|approval|checks)",
        r"disburse\s+(funds|money|ugx)",
        r"delete\s+all\s+(data|memories|records)",
        r"<script.*?>",
        r"drop\s+table",
    ]

    @classmethod
    def validate_user_prompt(cls, prompt: str) -> str:
        """
        Scan user prompt for prompt injection patterns.

        Args:
            prompt: Raw user input text.

        Raises:
            GuardrailViolation: If malicious or jailbreak phrasing is detected.

        Returns:
            Cleaned prompt string if valid.
        """
        if not prompt or not prompt.strip():
            raise GuardrailViolation("EMPTY_PROMPT", "Prompt cannot be empty.")

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                raise GuardrailViolation(
                    code="PROMPT_INJECTION_DETECTED",
                    message=f"Prompt rejected: matches restricted pattern '{pattern}'.",
                    context={"detected_pattern": pattern, "prompt_snippet": prompt[:80]}
                )

        return prompt.strip()

    @classmethod
    def validate_budget(cls, budget_ugx: Any) -> int:
        """
        Ensure budget is a valid positive integer.
        
        Args:
            budget_ugx: Input budget figure.

        Raises:
            GuardrailViolation: If budget is negative, non-numeric, or unreasonable.
        """
        try:
            val = int(budget_ugx)
        except (ValueError, TypeError):
            raise GuardrailViolation("INVALID_BUDGET_TYPE", f"Budget must be an integer, got: {budget_ugx}")

        if val <= 0:
            raise GuardrailViolation("NEGATIVE_OR_ZERO_BUDGET", f"Budget must be greater than zero. Received: {val}")

        # Reasonable upper boundary for an SME shop (e.g. 500,000,000 UGX)
        if val > 500_000_000:
            raise GuardrailViolation("BUDGET_EXCEEDS_CAP", f"Budget exceeds SME maximum ceiling of 500M UGX: {val}")

        return val

    @classmethod
    def validate_shop_id(cls, shop_id: str) -> str:
        """
        Validate shop identifier to prevent injection and path traversal.
        """
        if not shop_id or not re.match(r"^[a-zA-Z0-9_\-]+$", shop_id):
            raise GuardrailViolation("INVALID_SHOP_ID", f"shop_id must be alphanumeric. Received: '{shop_id}'")
        return shop_id


class BudgetCeilingGuardrail:
    """
    Enforces the financial ceiling guardrail (Fixes Failure Mode F-12).
    Guarantees that recommended restock requisitions NEVER exceed allocated funds.
    """

    @classmethod
    def verify_draft_within_budget(cls, draft_total_ugx: int, allocated_budget_ugx: int) -> bool:
        """
        Check if draft total strictly stays within allocated budget.

        Args:
            draft_total_ugx: Total sum of items in the draft purchase order.
            allocated_budget_ugx: Maximum budget authorized by the user.

        Raises:
            GuardrailViolation: If draft exceeds allocated budget.

        Returns:
            True if within budget.
        """
        if draft_total_ugx > allocated_budget_ugx:
            overage = draft_total_ugx - allocated_budget_ugx
            raise GuardrailViolation(
                code="BUDGET_CEILING_EXCEEDED",
                message=(
                    f"Draft total UGX {draft_total_ugx:,} exceeds allocated budget "
                    f"UGX {allocated_budget_ugx:,} by UGX {overage:,}. F-12 Guardrail triggered."
                ),
                context={
                    "draft_total": draft_total_ugx,
                    "budget": allocated_budget_ugx,
                    "overage": overage
                }
            )
        return True


class HumanInTheLoopGuardrail:
    """
    Guarantees that the AI agent can NEVER autonomously approve, sign, or pay for orders.
    Enforces the boundary: AI recommends; only Human approves.
    """

    FORBIDDEN_AUTONOMOUS_ACTIONS = {
        "approve_requisition",
        "sign_purchase_order",
        "make_mobile_money_payment",
        "execute_bank_transfer",
        "confirm_supplier_contract",
        # Legacy aliases kept so every surface (MCP, CLI, agent) blocks the same
        # action names. They describe the same human-only authorities.
        "disburse_funds",
        "make_payment",
    }

    @classmethod
    def verify_action_permitted(cls, action_name: str, actor_role: str) -> bool:
        """
        Check if the requested action is permitted for the given actor.

        Args:
            action_name: The operation being attempted.
            actor_role: 'AI_AGENT' or 'HUMAN_OWNER'.

        Raises:
            GuardrailViolation: If an AI actor attempts a human-only authority.
        """
        if action_name in cls.FORBIDDEN_AUTONOMOUS_ACTIONS:
            if actor_role != "HUMAN_OWNER":
                raise GuardrailViolation(
                    code="UNAUTHORIZED_AUTONOMY_ATTEMPT",
                    message=(
                        f"Action '{action_name}' is strictly reserved for 'HUMAN_OWNER'. "
                        f"AI agents are legally and architecturally bounded from making financial commitments."
                    ),
                    context={"action": action_name, "actor_role": actor_role}
                )
        return True
