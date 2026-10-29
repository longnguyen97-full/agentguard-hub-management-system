import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LoopDetector:
    """Detects repeated tool calls and potential infinite reasoning loops."""

    def __init__(self, max_consecutive_repeats: int = 2):
        self.max_consecutive_repeats = max_consecutive_repeats
        self.call_history: List[str] = []

    def check_loop(self, tool_name: str, tool_input: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        try:
            signature = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"
        except Exception:
            signature = f"{tool_name}:{str(tool_input)}"

        self.call_history.append(signature)

        # Check consecutive identical calls
        if len(self.call_history) >= self.max_consecutive_repeats + 1:
            recent = self.call_history[-(self.max_consecutive_repeats + 1):]
            if len(set(recent)) == 1:
                reason = f"Infinite loop detected: tool '{tool_name}' called {len(recent)} times with identical arguments."
                logger.warning(reason)
                return True, reason

        return False, None


class BudgetGuardrail:
    """Monitors token consumption and estimated financial expenditure."""

    # Default pricing per 1k tokens (example based on standard mini models)
    PRICING_PER_1K = {
        "prompt": 0.00015,     # $0.15 per 1M prompt tokens
        "completion": 0.00060  # $0.60 per 1M completion tokens
    }

    @classmethod
    def calculate_cost(cls, prompt_tokens: int, completion_tokens: int) -> float:
        cost = (prompt_tokens / 1000.0 * cls.PRICING_PER_1K["prompt"]) + \
               (completion_tokens / 1000.0 * cls.PRICING_PER_1K["completion"])
        return round(cost, 6)

    @classmethod
    def check_limits(
        cls,
        current_step: int,
        max_steps: int,
        current_tokens: int,
        token_limit: int,
        current_cost: float,
        budget_usd: float
    ) -> Tuple[bool, Optional[str]]:
        if current_step >= max_steps:
            return False, f"Maximum allowed steps reached ({max_steps} steps)."

        if current_tokens >= token_limit:
            return False, f"Token ceiling reached ({current_tokens} / {token_limit} tokens)."

        if current_cost >= budget_usd:
            return False, f"Cost budget limit reached (${current_cost:.4f} / ${budget_usd:.4f})."

        return True, None

    @classmethod
    def check_warning_threshold(
        cls,
        current_cost: float,
        budget_usd: float,
        threshold_ratio: float = 0.70
    ) -> Tuple[bool, Optional[str]]:
        """Returns True and warning message if current spend reaches or exceeds warning threshold ratio."""
        if budget_usd <= 0:
            return False, None
        ratio = current_cost / budget_usd
        if ratio >= threshold_ratio:
            return True, f"Budget threshold warning: Current spend reached {ratio*100:.1f}% of budget limit (${current_cost:.4f} / ${budget_usd:.4f})."
        return False, None


class ActionApprovalGuardrail:
    """Checks whether an action/tool requires human intervention and authorization."""

    @staticmethod
    def requires_approval(tool_name: str, sensitive_tools: List[str]) -> bool:
        return tool_name.lower() in [tool.lower() for tool in sensitive_tools]

