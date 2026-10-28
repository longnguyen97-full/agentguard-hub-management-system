from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_utc_now():
    return datetime.now(timezone.utc)


class AgentRunStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    KILLED = "KILLED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ToolApprovalRequest(BaseModel):
    tool_name: str
    tool_input: Dict[str, Any]
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None


class AgentStepLog(BaseModel):
    step_number: int
    thought: Optional[str] = None
    action_type: str = "tool_call"  # "tool_call" | "message" | "finish"
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    latency_ms: Optional[float] = None
    tokens_used: int = 0
    is_billable: bool = True  # True: LLM generation, Paid API | False: Local Tool, Deterministic code, Cache
    cost_usd: float = 0.0
    cost_vnd: float = 0.0
    execution_type: str = "llm_reasoning"  # "llm_reasoning" | "deterministic_tool" | "cache_hit"
    timestamp: datetime = Field(default_factory=get_utc_now)


class AgentRunRequest(BaseModel):
    prompt: str
    agent_name: str = "AssistantAgent"
    model: str = "gpt-4o-mini"
    max_steps: int = 10
    budget_usd: float = 0.50
    token_limit: int = 10000
    require_approval_tools: List[str] = Field(
        default_factory=lambda: ["execute_database_update", "delete_resource", "send_external_email"]
    )
    user_id: Optional[str] = "user_demo"
    is_simulation: bool = True


class AgentRunState(BaseModel):
    run_id: str
    agent_name: str
    prompt: str
    status: AgentRunStatus = AgentRunStatus.RUNNING
    current_step: int = 0
    max_steps: int = 10
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_cost_vnd: float = 0.0
    is_simulation: bool = True
    pending_approval: Optional[ToolApprovalRequest] = None
    steps: List[AgentStepLog] = Field(default_factory=list)
    final_output: Optional[str] = None
    error_message: Optional[str] = None
    langfuse_trace_id: Optional[str] = None
    langfuse_trace_url: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class ApprovalDecision(BaseModel):
    approved: bool
    user: str = "admin"
    comment: Optional[str] = None
