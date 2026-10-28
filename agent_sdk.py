"""
Agent Monitoring Lightweight Client SDK.
Dành cho các hệ thống Agent bên ngoài muốn kết nối và bắn telemetry về Hub giám sát.
"""

import httpx
from typing import Optional, Dict, Any


class AgentTracker:
    """Client SDK để kết nối vào Agent Monitoring Hub."""

    def __init__(self, endpoint: str = "http://localhost:8000"):
        self.endpoint = endpoint.rstrip("/")
        self.client = httpx.Client(timeout=10.0)

    def start_run(
        self,
        agent_name: str,
        prompt: str,
        max_steps: int = 10,
        budget_usd: float = 0.50,
        user_id: Optional[str] = "external_user"
    ) -> "AgentSession":
        """Đăng ký khởi tạo một phiên chạy của Agent từ hệ thống bên ngoài."""
        resp = self.client.post(
            f"{self.endpoint}/api/agents/external/start",
            json={
                "agent_name": agent_name,
                "prompt": prompt,
                "max_steps": max_steps,
                "budget_usd": budget_usd,
                "user_id": user_id
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return AgentSession(tracker=self, run_id=data["run_id"], agent_name=agent_name)


class AgentSession:
    """Phiên làm việc của một Agent cụ thể."""

    def __init__(self, tracker: AgentTracker, run_id: str, agent_name: str):
        self.tracker = tracker
        self.run_id = run_id
        self.agent_name = agent_name
        self.step_counter = 0

    def log_step(
        self,
        thought: str,
        tool_name: Optional[str] = None,
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Optional[Any] = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        latency_ms: Optional[float] = None,
        is_billable: bool = True
    ):
        """Ghi nhận một bước thực thi (suy luận hoặc gọi công cụ)."""
        self.step_counter += 1
        payload = {
            "step_number": self.step_counter,
            "thought": thought,
            "action_type": "tool_call" if tool_name else "reasoning",
            "tool_name": tool_name,
            "tool_input": tool_input or {},
            "tool_output": tool_output,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms or 120.0,
            "is_billable": is_billable
        }
        self.tracker.client.post(
            f"{self.tracker.endpoint}/api/agents/external/{self.run_id}/step",
            json=payload
        )

    def finish(self, final_output: str):
        """Báo cáo hoàn thành tác vụ thành công."""
        self.tracker.client.post(
            f"{self.tracker.endpoint}/api/agents/external/{self.run_id}/finish",
            json={"status": "COMPLETED", "final_output": final_output}
        )

    def fail(self, error_message: str):
        """Báo cáo tác vụ thất bại."""
        self.tracker.client.post(
            f"{self.tracker.endpoint}/api/agents/external/{self.run_id}/finish",
            json={"status": "FAILED", "error": error_message}
        )

