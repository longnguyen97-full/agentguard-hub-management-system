import asyncio
import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
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
from app.core.db import db
from app.core.auth import verify_api_key
from app.core.export import export_run_to_json, export_run_to_csv, export_all_runs_to_csv
from app.core.alerts import notifier, AlertNotifier
from app.core.pricing import pricing_registry
from app.agents.sample_agent import SampleMonitoredAgent

router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.get("/alerts/config")
async def get_alerts_config():
    """Returns current webhook alert destination and status."""
    return {
        "webhook_url": settings.ALERT_WEBHOOK_URL or "",
        "configured": bool(settings.ALERT_WEBHOOK_URL),
        "supported_channels": ["Discord (Rich Embeds)", "Slack (Block Kit)", "n8n / Custom JSON Webhooks"]
    }


@router.post("/alerts/config")
async def update_alerts_config(payload: dict, _api_key: Optional[str] = Depends(verify_api_key)):
    """Dynamically updates the alert webhook destination URL."""
    url = (payload.get("webhook_url") or "").strip()
    settings.ALERT_WEBHOOK_URL = url or None
    return {
        "status": "ok",
        "configured": bool(settings.ALERT_WEBHOOK_URL),
        "webhook_url": settings.ALERT_WEBHOOK_URL
    }


@router.post("/alerts/test")
async def send_test_alert(payload: Optional[dict] = None, _api_key: Optional[str] = Depends(verify_api_key)):
    """Sends a sample test notification to verify the webhook integration."""
    target_url = (payload and payload.get("webhook_url")) or settings.ALERT_WEBHOOK_URL
    if not target_url:
        raise HTTPException(status_code=400, detail="No webhook URL configured to test.")
    
    test_notifier = notifier if target_url == settings.ALERT_WEBHOOK_URL else AlertNotifier(target_url)
    delivered = await test_notifier.send_alert_async(
        title="AgentGuard Multi-Channel Alert Test",
        message="✅ Your webhook alert channel is successfully connected! You will receive instant notifications for Kill Switch activations, Human Approvals, and Safety Guardrails.",
        level="SUCCESS",
        metadata={
            "System": "AgentGuard Control Plane",
            "Status": "Operational 100%"
        }
    )
    return {"status": "ok", "delivered": delivered}


# --- Dynamic Model Pricing & Token Economics ---
@router.get("/models/pricing")
async def get_models_pricing():
    """Returns verified real-time pricing and context windows for major LLM providers."""
    return {
        "models": pricing_registry.get_all_models(),
        "usd_to_vnd_rate": settings.USD_TO_VND_RATE,
        "last_sync": pricing_registry._last_sync.isoformat() if pricing_registry._last_sync else None
    }


@router.post("/models/pricing/sync")
async def sync_models_pricing(_api_key: Optional[str] = Depends(verify_api_key)):
    """Synchronizes pricing with open-source community pricing index (LiteLLM index)."""
    res = await pricing_registry.sync_online_pricing()
    return res


@router.get("/simulation")
async def get_simulation_mode():
    """Returns whether system is running in mock simulation mode or live production mode."""
    return {"simulation_mode": settings.SIMULATION_MODE}


# --- Langfuse & ClickHouse Live Telemetry ---
@router.get("/telemetry/langfuse")
async def get_langfuse_telemetry():
    """Returns live aggregated telemetry metrics from Langfuse Health and ClickHouse analytics."""
    return tracer.get_langfuse_telemetry()


@router.post("/simulation")
async def set_simulation_mode(payload: dict):
    """Dynamically toggle between Simulation and Live Mode."""
    enabled = bool(payload.get("enabled", True))
    settings.SIMULATION_MODE = enabled
    registry.broadcast_event({
        "type": "simulation_mode_changed",
        "simulation_mode": enabled
    })
    return {"status": "ok", "simulation_mode": enabled}


@router.post("/run", response_model=AgentRunState)
async def start_agent_run(request: AgentRunRequest):
    """Initiates an agent task run with observability."""
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    request.is_simulation = settings.SIMULATION_MODE
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


@router.get("/auth/status")
async def get_auth_status():
    """Returns whether API key authentication is currently enforced."""
    return {
        "api_key_required": bool(settings.API_KEY),
        "auth_header_supported": ["X-API-Key", "Authorization: Bearer <key>"]
    }


@router.post("/runs/{run_id}/kill")
async def trigger_kill_switch(run_id: str, _api_key: Optional[str] = Depends(verify_api_key)):
    """Emergency kill switch: terminates the agent immediately."""
    success = registry.request_kill(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent run not found or already terminated")
    return {"status": "ok", "message": f"Kill signal sent to agent run {run_id}."}


@router.post("/runs/{run_id}/approve")
async def approve_sensitive_action(
    run_id: str,
    decision: ApprovalDecision,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Authorizes or denies a paused agent action (Human-in-the-Loop)."""
    success = registry.resolve_approval(run_id, decision)
    if not success:
        raise HTTPException(status_code=400, detail="Run is not waiting for approval or does not exist")
    action_text = "approved" if decision.approved else "rejected"
    return {"status": "ok", "message": f"Action successfully {action_text}."}


# --- Audit & Compliance Export Endpoints ---
@router.get("/export/all")
@router.get("/runs/export/all")
async def export_all_runs():
    """Exports CSV summary of all agent runs in the system."""
    csv_data = export_all_runs_to_csv()
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="agentguard_all_runs_audit.csv"'}
    )


@router.get("/runs/{run_id}/export")
@router.get("/export/{run_id}")
async def export_agent_run(run_id: str, format: str = Query("json", pattern="^(json|csv)$")):
    """Exports structured audit trace of a run in JSON or CSV format."""
    if format == "csv":
        csv_data = export_run_to_csv(run_id)
        if csv_data is None:
            raise HTTPException(status_code=404, detail="Agent run not found")
        return Response(
            content=csv_data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="agent_audit_{run_id}.csv"'}
        )
    
    json_data = export_run_to_json(run_id)
    if json_data is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return json_data


# --- External System Ingestion Endpoints ---
@router.post("/external/start", response_model=AgentRunState)
async def external_agent_start(
    request: AgentRunRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Endpoint for external systems to register an agent run."""
    run_id = f"ext_{uuid.uuid4().hex[:10]}"
    state = AgentRunState(
        run_id=run_id,
        agent_name=request.agent_name,
        prompt=request.prompt,
        status=AgentRunStatus.RUNNING,
        max_steps=request.max_steps,
        is_simulation=False,  # External agent run is a real production run
        langfuse_trace_id=run_id,
        langfuse_trace_url=tracer.get_trace_url(run_id)
    )
    registry.register_run(state)
    return state


@router.post("/external/{run_id}/step")
async def external_agent_step(
    run_id: str,
    step: AgentStepLog,
    _api_key: Optional[str] = Depends(verify_api_key),
):
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
    db.save_run(handle.state)
    db.save_step(run_id, step)

    registry.broadcast_event({
        "type": "step_completed",
        "run_id": run_id,
        "step": step.model_dump(mode="json"),
        "total_tokens": handle.state.total_tokens,
        "total_cost": handle.state.total_cost_usd
    })
    return {"status": "ok"}


@router.post("/external/{run_id}/finish")
async def external_agent_finish(
    run_id: str,
    payload: dict,
    _api_key: Optional[str] = Depends(verify_api_key),
):
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
    db.save_run(handle.state)

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
            yield f"data: {json.dumps({'type': 'connected'}, ensure_ascii=False)}\n\n"
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            registry.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
