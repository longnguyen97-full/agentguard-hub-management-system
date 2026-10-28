import abc
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from app.config import settings
from app.schemas.agent import (
    AgentRunRequest,
    AgentRunState,
    AgentRunStatus,
    AgentStepLog,
    ApprovalStatus,
    ToolApprovalRequest,
    get_utc_now,
)
from app.core.guardrails import LoopDetector, BudgetGuardrail, ActionApprovalGuardrail
from app.core.registry import registry, AgentRunHandle
from app.core.tracer import tracer

logger = logging.getLogger(__name__)


class BaseAgent(abc.ABC):
    """Base class for monitored agents with built-in observability and guardrails."""

    def __init__(self, request: AgentRunRequest, run_id: str):
        self.request = request
        self.run_id = run_id
        self.state = AgentRunState(
            run_id=run_id,
            agent_name=request.agent_name,
            prompt=request.prompt,
            status=AgentRunStatus.RUNNING,
            max_steps=request.max_steps,
            langfuse_trace_id=run_id,
            langfuse_trace_url=tracer.get_trace_url(run_id)
        )
        self.handle: AgentRunHandle = registry.register_run(self.state)
        self.loop_detector = LoopDetector(max_consecutive_repeats=2)

    async def execute(self):
        """Main execution lifecycle with observability hooks and guardrails."""
        logger.info(f"Starting agent run {self.run_id} for prompt: {self.request.prompt}")

        # Initialize Langfuse trace/observation
        trace_id = tracer.create_trace(
            run_id=self.run_id,
            name=f"Agent:{self.request.agent_name}",
            user_id=self.request.user_id,
            input_data={"prompt": self.request.prompt, "model": self.request.model},
            metadata={"max_steps": self.request.max_steps, "budget_usd": self.request.budget_usd}
        )
        if trace_id:
            self.state.langfuse_trace_id = trace_id
            self.state.langfuse_trace_url = tracer.get_trace_url(self.run_id)

        try:
            for step_num in range(1, self.request.max_steps + 1):
                # 1. Check Kill Switch
                if self.handle.kill_requested:
                    logger.warning(f"Run {self.run_id} stopped: Kill switch was requested.")
                    self._finish_run(AgentRunStatus.KILLED, error="Terminated by operator kill switch.")
                    return

                # 2. Check Budget & Step Limits
                allowed, limit_reason = BudgetGuardrail.check_limits(
                    current_step=step_num,
                    max_steps=self.request.max_steps,
                    current_tokens=self.state.total_tokens,
                    token_limit=self.request.token_limit,
                    current_cost=self.state.total_cost_usd,
                    budget_usd=self.request.budget_usd
                )
                if not allowed:
                    logger.warning(f"Run {self.run_id} halted: {limit_reason}")
                    self._finish_run(AgentRunStatus.FAILED, error=limit_reason)
                    return

                self.state.current_step = step_num
                self.state.updated_at = get_utc_now()

                # 3. Plan / Reason Next Step
                start_time = time.time()
                thought, action_type, tool_name, tool_input, is_finish = await self.reason_next_step(step_num)

                # Record generation / reasoning tokens
                prompt_tokens = 150 + step_num * 25
                comp_tokens = 80
                step_tokens = prompt_tokens + comp_tokens
                step_cost = BudgetGuardrail.calculate_cost(prompt_tokens, comp_tokens)

                self.state.total_tokens += step_tokens
                self.state.total_cost_usd = round(self.state.total_cost_usd + step_cost, 6)
                self.state.total_cost_vnd = round(self.state.total_cost_usd * settings.USD_TO_VND_RATE, 2)

                # Langfuse generation log
                tracer.log_generation(
                    run_id=self.run_id,
                    name=f"Step_{step_num}_Reasoning",
                    model=self.request.model,
                    prompt={"step": step_num, "prompt": self.request.prompt},
                    completion={"thought": thought, "tool": tool_name},
                    usage={"prompt_tokens": prompt_tokens, "completion_tokens": comp_tokens, "total_tokens": step_tokens}
                )

                if is_finish:
                    step_cost_vnd = round(step_cost * settings.USD_TO_VND_RATE, 2)
                    step_log = AgentStepLog(
                        step_number=step_num,
                        thought=thought,
                        action_type="finish",
                        tool_output=tool_input.get("final_answer", "Completed"),
                        latency_ms=round((time.time() - start_time) * 1000, 2),
                        tokens_used=step_tokens,
                        is_billable=True,
                        cost_usd=step_cost,
                        cost_vnd=step_cost_vnd,
                        execution_type="llm_reasoning"
                    )
                    self.state.steps.append(step_log)
                    self.state.final_output = str(tool_input.get("final_answer", "Completed successfully"))
                    self._finish_run(AgentRunStatus.COMPLETED)
                    return

                # 4. Loop Detection Check
                is_loop, loop_msg = self.loop_detector.check_loop(tool_name, tool_input)
                if is_loop:
                    self._finish_run(AgentRunStatus.FAILED, error=loop_msg)
                    return

                # 5. Human-in-the-Loop Action Approval Check
                if ActionApprovalGuardrail.requires_approval(tool_name, self.request.require_approval_tools):
                    logger.info(f"Sensitive action '{tool_name}' triggered in run {self.run_id}. Pausing for operator approval...")
                    approval_req = ToolApprovalRequest(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        reason=f"Action '{tool_name}' is marked as sensitive and requires operator authorization."
                    )
                    self.state.pending_approval = approval_req
                    registry.update_status(self.run_id, AgentRunStatus.WAITING_APPROVAL)

                    # Await approval
                    await self.handle.approval_event.wait()
                    self.handle.approval_event.clear()

                    # Check kill switch during wait
                    if self.handle.kill_requested:
                        self._finish_run(AgentRunStatus.KILLED, error="Terminated while waiting for approval.")
                        return

                    decision = self.handle.approval_decision
                    if not decision or not decision.approved:
                        logger.warning(f"Tool execution for '{tool_name}' rejected by operator.")
                        self.state.pending_approval = None
                        registry.update_status(self.run_id, AgentRunStatus.RUNNING)
                        tool_output = f"REJECTED by operator: {decision.comment if decision else 'No reason provided'}"
                    else:
                        logger.info(f"Tool execution for '{tool_name}' approved by {decision.user}.")
                        self.state.pending_approval = None
                        registry.update_status(self.run_id, AgentRunStatus.RUNNING)
                        tool_output = await self.execute_tool(tool_name, tool_input)
                else:
                    # Execute tool automatically
                    tool_output = await self.execute_tool(tool_name, tool_input)

                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                step_cost_vnd = round(step_cost * settings.USD_TO_VND_RATE, 2)

                # Record step log with cost breakdown
                step_log = AgentStepLog(
                    step_number=step_num,
                    thought=thought,
                    action_type="tool_call",
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                    latency_ms=elapsed_ms,
                    tokens_used=step_tokens,
                    is_billable=True,
                    cost_usd=step_cost,
                    cost_vnd=step_cost_vnd,
                    execution_type="llm_reasoning"
                )
                self.state.steps.append(step_log)

                # Langfuse Tool Span log
                tracer.log_tool_span(
                    run_id=self.run_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                    metadata={"step": step_num, "latency_ms": elapsed_ms}
                )

                registry.broadcast_event({
                    "type": "step_completed",
                    "run_id": self.run_id,
                    "step": step_log.model_dump(mode="json"),
                    "total_tokens": self.state.total_tokens,
                    "total_cost": self.state.total_cost_usd
                })

                # Small delay to simulate async reasoning
                await asyncio.sleep(0.8)

            # If reached max steps without finishing
            self._finish_run(AgentRunStatus.FAILED, error="Exceeded maximum steps without reaching conclusion.")

        except asyncio.CancelledError:
            logger.info(f"Agent run {self.run_id} cancelled.")
            self._finish_run(AgentRunStatus.KILLED, error="Task cancelled.")
        except Exception as e:
            logger.exception(f"Unexpected error in agent run {self.run_id}: {e}")
            self._finish_run(AgentRunStatus.FAILED, error=str(e))

    def _finish_run(self, status: AgentRunStatus, error: Optional[str] = None):
        self.state.status = status
        self.state.updated_at = get_utc_now()
        if error:
            self.state.error_message = error

        tracer.update_trace(
            run_id=self.run_id,
            output=self.state.final_output or self.state.error_message,
            metadata={
                "status": status.value,
                "total_steps": len(self.state.steps),
                "total_tokens": self.state.total_tokens,
                "total_cost_usd": self.state.total_cost_usd
            }
        )

        score_val = 1.0 if status == AgentRunStatus.COMPLETED else 0.0
        tracer.score_trace(
            run_id=self.run_id,
            name="completion_success",
            value=score_val,
            comment=f"Finished with status {status.value}"
        )

        registry.broadcast_event({
            "type": "run_finished",
            "run_id": self.run_id,
            "status": status.value,
            "error": error,
            "final_output": self.state.final_output
        })

    @abc.abstractmethod
    async def reason_next_step(self, step: int) -> tuple[str, str, Optional[str], Dict[str, Any], bool]:
        """Returns: (thought, action_type, tool_name, tool_input, is_finish)"""
        pass

    @abc.abstractmethod
    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        pass
