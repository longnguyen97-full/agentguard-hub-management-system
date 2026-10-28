import asyncio
import json
import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.agent import (
    AgentRunRequest,
    AgentRunState,
    AgentRunStatus,
    AgentStepLog,
    ApprovalDecision,
    get_utc_now,
)
from app.config import settings
from app.core.registry import registry
from app.core.tracer import tracer
from app.agents.sample_agent import SampleMonitoredAgent

router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.post("/run", response_model=AgentRunState)
async def start_agent_run(request: AgentRunRequest):
    """Initiates an asynchronous agent task run with observability."""
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    agent = SampleMonitoredAgent(request=request, run_id=run_id)

    # Launch agent loop as background task
    task = asyncio.create_task(agent.execute())
    agent.handle.task = task

    return agent.state


@router.get("/runs", response_model=List[AgentRunState])
async def list_agent_runs():
    """Returns all registered agent runs."""
    return registry.list_runs()


@router.get("/runs/{run_id}", response_model=AgentRunState)
async def get_agent_run(run_id: str):
    """Returns detailed state, steps, and telemetry for a specific run."""
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.post("/runs/{run_id}/kill")
async def trigger_kill_switch(run_id: str):
    """Emergency kill switch: terminates the agent immediately."""
    success = registry.request_kill(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent run not found or already terminated")
    return {"status": "ok", "message": f"Kill signal sent to agent run {run_id}."}


@router.post("/runs/{run_id}/approve")
async def approve_sensitive_action(run_id: str, decision: ApprovalDecision):
    """Authorizes or denies a paused agent action (Human-in-the-Loop)."""
    success = registry.resolve_approval(run_id, decision)
    if not success:
        raise HTTPException(status_code=400, detail="Run is not waiting for approval or does not exist")
    action_text = "approved" if decision.approved else "rejected"
    return {"status": "ok", "message": f"Action successfully {action_text}."}


# --- External System Ingestion Endpoints ---
@router.post("/external/start", response_model=AgentRunState)
async def external_agent_start(request: AgentRunRequest):
    """Endpoint for external systems to register an agent run."""
    run_id = f"ext_{uuid.uuid4().hex[:10]}"
    state = AgentRunState(
        run_id=run_id,
        agent_name=request.agent_name,
        prompt=request.prompt,
        status=AgentRunStatus.RUNNING,
        max_steps=request.max_steps,
        langfuse_trace_id=run_id,
        langfuse_trace_url=tracer.get_trace_url(run_id)
    )
    registry.register_run(state)
    return state


@router.post("/external/{run_id}/step")
async def external_agent_step(run_id: str, step: AgentStepLog):
    """Endpoint for external systems to stream step logs and cost/token metrics."""
    handle = registry.get_handle(run_id)
    if not handle:
        raise HTTPException(status_code=404, detail="Agent run not found")

    handle.state.steps.append(step)
    handle.state.current_step = step.step_number
    handle.state.total_tokens += step.tokens_used
    handle.state.total_cost_usd = round(handle.state.total_cost_usd + step.cost_usd, 6)
    handle.state.total_cost_vnd = round(handle.state.total_cost_usd * settings.USD_TO_VND_RATE, 2)
    handle.state.updated_at = get_utc_now()

    registry.broadcast_event({
        "type": "step_completed",
        "run_id": run_id,
        "step": step.model_dump(mode="json"),
        "total_tokens": handle.state.total_tokens,
        "total_cost": handle.state.total_cost_usd
    })
    return {"status": "ok"}


@router.post("/external/{run_id}/finish")
async def external_agent_finish(run_id: str, payload: dict):
    """Endpoint for external systems to mark an agent run completed or failed."""
    handle = registry.get_handle(run_id)
    if not handle:
        raise HTTPException(status_code=404, detail="Agent run not found")

    status_str = payload.get("status", "COMPLETED").upper()
    status = AgentRunStatus.COMPLETED if status_str == "COMPLETED" else AgentRunStatus.FAILED
    final_output = payload.get("final_output")
    error = payload.get("error")

    handle.state.status = status
    handle.state.final_output = final_output
    handle.state.error_message = error
    handle.state.updated_at = get_utc_now()

    registry.broadcast_event({
        "type": "run_finished",
        "run_id": run_id,
        "status": status.value,
        "error": error,
        "final_output": final_output
    })
    return {"status": "ok"}


@router.get("/stream")
async def event_stream():
    """Server-Sent Events (SSE) stream for real-time dashboard updates."""
    queue = registry.subscribe()

    async def event_generator():
        try:
            # Send initial ping
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            registry.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

