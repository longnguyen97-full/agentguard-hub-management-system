import asyncio
import logging
from typing import Any, Dict, Optional
from app.agents.base import BaseAgent
from app.schemas.agent import AgentRunRequest

logger = logging.getLogger(__name__)


class SampleMonitoredAgent(BaseAgent):
    """
    An intelligent multi-step reasoning agent demonstration.
    Demonstrates:
    - Multi-step tool calls
    - Sensitive action triggering Human-in-the-Loop approval (execute_database_update)
    - Infinite loop detection trigger
    - Clean completion and token tracking
    """

    def __init__(self, request: AgentRunRequest, run_id: str):
        super().__init__(request, run_id)
        self.scenario = self._detect_scenario(request.prompt)

    def _detect_scenario(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "loop" in prompt_lower:
            return "loop"
        elif "update" in prompt_lower or "delete" in prompt_lower or "sensitive" in prompt_lower or "xóa" in prompt_lower or "cập nhật" in prompt_lower:
            return "sensitive_action"
        return "standard_search"

    async def reason_next_step(self, step: int) -> tuple[str, str, Optional[str], Dict[str, Any], bool]:
        """Simulate agent's ReAct (Reasoning + Acting) thought process."""
        await asyncio.sleep(0.6)  # Simulate LLM inference latency

        if self.scenario == "loop":
            # Deliberately produces the exact same call to test LoopDetector
            thought = f"I need to check database connection status repeatedly (Iteration {step})."
            return thought, "tool_call", "check_health", {"host": "db.internal", "port": 5432}, False

        elif self.scenario == "sensitive_action":
            if step == 1:
                thought = "I need to inspect the database record before making any modifications."
                return thought, "tool_call", "query_database", {"table": "users", "query": "id=1024"}, False
            elif step == 2:
                thought = "User record verified. Proceeding to apply update on user quota. This requires privileged authorization."
                return thought, "tool_call", "execute_database_update", {
                    "table": "users",
                    "operation": "SET quota = 5000 WHERE id = 1024",
                    "reason": "Automated account upgrade requested"
                }, False
            else:
                thought = "All operations completed successfully. Formulating final answer."
                return thought, "finish", None, {"final_answer": "Successfully verified record and updated quota for user #1024."}, True

        else:
            # Standard scenario
            if step == 1:
                thought = f"Analyzing user prompt: '{self.request.prompt}'. First, querying knowledge base for relevant context."
                return thought, "tool_call", "search_knowledge_base", {"query": self.request.prompt, "limit": 3}, False
            elif step == 2:
                thought = "Information retrieved. Now calculating metric statistics."
                return thought, "tool_call", "calculate_metric", {"dataset_size": 240, "metric": "average_latency"}, False
            else:
                thought = "Synthesized data successfully. Preparing executive summary."
                return thought, "finish", None, {
                    "final_answer": f"Processed request '{self.request.prompt}'. Knowledge base consulted and metrics calculated: avg latency 42ms with 99.8% availability."
                }, True

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Simulates tool execution with realistic outputs."""
        await asyncio.sleep(0.4)

        if tool_name == "search_knowledge_base":
            return [
                {"id": "doc_1", "title": "System Architecture Overview", "score": 0.94},
                {"id": "doc_2", "title": "Security Guidelines & RBAC", "score": 0.88}
            ]
        elif tool_name == "query_database":
            return {"status": "found", "id": 1024, "username": "alex_doe", "quota": 1000, "status": "active"}
        elif tool_name == "execute_database_update":
            return {"status": "success", "affected_rows": 1, "applied_sql": tool_input.get("operation")}
        elif tool_name == "calculate_metric":
            return {"average_latency_ms": 42.1, "p99_latency_ms": 115.0, "sample_count": tool_input.get("dataset_size", 100)}
        elif tool_name == "check_health":
            return {"status": "healthy", "latency_ms": 2.3}
        else:
            return {"status": "ok", "message": f"Executed tool {tool_name}"}

