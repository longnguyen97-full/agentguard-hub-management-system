import asyncio
import logging
from typing import Any, Dict, Optional
from app.agents.base import BaseAgent
from app.schemas.agent import AgentRunRequest

logger = logging.getLogger(__name__)


class SampleMonitoredAgent(BaseAgent):
    """
    An intelligent multi-step reasoning agent demonstration covering all major AgentOps cases:
    1. Standard multi-step research & metrics synthesis.
    2. Sensitive action triggering Human-in-the-Loop approval (execute_database_update).
    3. Infinite loop detection trigger (repetitive check_health calls).
    4. Massive token consumption & budget limit trigger (scrape_high_volume_dataset).
    5. Prompt injection / adversarial jailbreak defense.
    6. Third-party tool failure & retry resilience.
    """

    def __init__(self, request: AgentRunRequest, run_id: str):
        super().__init__(request, run_id)
        self.scenario = self._detect_scenario(request.prompt)

    def _detect_scenario(self, prompt: str) -> str:
        p = prompt.lower()
        if "loop" in p or "vòng lặp" in p:
            return "loop"
        elif "budget" in p or "ngân sách" in p or "scraping" in p or "trích xuất" in p:
            return "budget_spike"
        elif "injection" in p or "leak" in p or "tiết lộ" in p or "chèn mã" in p or "ignore" in p or "bỏ qua" in p:
            return "prompt_injection"
        elif "timeout" in p or "failover" in p or "thanh toán" in p or "retry" in p or "sự cố" in p:
            return "tool_failure"
        elif any(k in p for k in ["update", "delete", "sensitive", "xóa", "cập nhật", "phê duyệt", "hạn ngạch"]):
            return "sensitive_action"
        return "standard_search"

    async def reason_next_step(self, step: int) -> tuple[str, str, Optional[str], Dict[str, Any], bool]:
        """Simulate agent's ReAct (Reasoning + Acting) thought process."""
        await asyncio.sleep(0.5)

        # 1. Infinite Loop Scenario
        if self.scenario == "loop":
            thought = f"I need to check database connection status repeatedly (Iteration {step})."
            return thought, "tool_call", "check_health", {"host": "db.internal", "port": 5432}, False

        # 2. Sensitive Action (HITL) Scenario
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

        # 3. Budget & Token Runaway Spike
        elif self.scenario == "budget_spike":
            if step == 1:
                thought = "User requested massive data extraction. Calling bulk scraping tool with high volume dataset."
                return thought, "tool_call", "scrape_high_volume_dataset", {"target": "enterprise_logs_2026", "pages": 500}, False
            else:
                thought = "Processing downloaded raw logs and generating full vectorized index."
                return thought, "tool_call", "vectorize_bulk_data", {"chunks": 25000}, False

        # 4. Prompt Injection Defense
        elif self.scenario == "prompt_injection":
            if step == 1:
                thought = "Evaluating prompt for safety and intent alignment. Detected prompt injection attempt to exfiltrate confidential credentials."
                return thought, "tool_call", "security_policy_checker", {"threat_type": "prompt_injection", "severity": "HIGH"}, False
            else:
                thought = "Safety violation confirmed. Aborting task and providing secure canned response."
                return thought, "finish", None, {
                    "final_answer": "SECURITY ALERT: Request rejected by AgentGuard Safety Policy (Unauthorized attempt to reveal system credentials)."
                }, True

        # 5. Third-Party Tool Failure & Resilience
        elif self.scenario == "tool_failure":
            if step == 1:
                thought = "Calling external payment gateway to verify customer billing state."
                return thought, "tool_call", "external_payment_api", {"customer_id": "cust_9921", "attempt": 1}, False
            elif step == 2:
                thought = "First call resulted in gateway timeout. Executing exponential backoff retry to secondary endpoint."
                return thought, "tool_call", "external_payment_api", {"customer_id": "cust_9921", "attempt": 2, "endpoint": "secondary"}, False
            else:
                thought = "Secondary gateway recovered and confirmed transaction status. Generating summary."
                return thought, "finish", None, {
                    "final_answer": "Successfully retrieved billing status via secondary gateway failover."
                }, True

        # 6. Standard Scenario
        else:
            if step == 1:
                thought = f"Analyzing request: '{self.request.prompt}'. Querying knowledge base for relevant context."
                return thought, "tool_call", "search_knowledge_base", {"query": self.request.prompt, "limit": 3}, False
            elif step == 2:
                thought = "Context retrieved. Calculating metric statistics and performance latencies."
                return thought, "tool_call", "calculate_metric", {"dataset_size": 240, "metric": "average_latency"}, False
            else:
                thought = "Data synthesized successfully. Formulating final response."
                return thought, "finish", None, {
                    "final_answer": f"Processed request '{self.request.prompt}'. Knowledge base consulted and metrics calculated: avg latency 42ms with 99.8% availability."
                }, True

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Simulates tool execution with realistic outputs."""
        await asyncio.sleep(0.3)

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
        elif tool_name == "scrape_high_volume_dataset":
            # Consume high token spend to trigger budget ceiling
            self.state.total_tokens += 8500
            self.state.total_cost_usd = round(self.state.total_cost_usd + 0.45, 6)
            return {"status": "downloaded", "rows": 50000, "size_mb": 142.5}
        elif tool_name == "vectorize_bulk_data":
            self.state.total_tokens += 12000
            self.state.total_cost_usd = round(self.state.total_cost_usd + 0.60, 6)
            return {"status": "indexed", "vectors": 25000}
        elif tool_name == "security_policy_checker":
            return {"violation": True, "action": "BLOCKED", "reason": "Prompt injection detected in input tokens."}
        elif tool_name == "external_payment_api":
            if tool_input.get("attempt") == 1:
                return {"status": "error", "code": 504, "message": "Gateway Timeout (upstream service unresponsive)"}
            return {"status": "success", "code": 200, "customer": "cust_9921", "balance": "$4,200.00"}
        else:
            return {"status": "ok", "message": f"Executed tool {tool_name}"}
