import asyncio
import pytest
from app.schemas.agent import AgentRunRequest, AgentRunStatus, ApprovalDecision
from app.agents.sample_agent import SampleMonitoredAgent
from app.core.registry import registry
from app.core.guardrails import LoopDetector, BudgetGuardrail


@pytest.mark.asyncio
async def test_standard_agent_execution():
    req = AgentRunRequest(prompt="Search knowledge base and calculate system latency metrics")
    agent = SampleMonitoredAgent(req, "test_run_standard")
    await agent.execute()

    assert agent.state.status == AgentRunStatus.COMPLETED
    assert len(agent.state.steps) == 3
    assert agent.state.total_tokens > 0
    assert agent.state.total_cost_usd > 0
    assert "Processed request" in agent.state.final_output


@pytest.mark.asyncio
async def test_loop_detector_guardrail():
    req = AgentRunRequest(prompt="Simulate infinite loop by calling check_health repetitively")
    agent = SampleMonitoredAgent(req, "test_run_loop")
    await agent.execute()

    assert agent.state.status == AgentRunStatus.FAILED
    assert "Infinite loop detected" in agent.state.error_message


@pytest.mark.asyncio
async def test_budget_limit_guardrail():
    # Set budget extremely low to trigger guardrail
    req = AgentRunRequest(
        prompt="Search knowledge base and calculate system latency metrics",
        budget_usd=0.00001
    )
    agent = SampleMonitoredAgent(req, "test_run_budget")
    await agent.execute()

    assert agent.state.status == AgentRunStatus.FAILED
    assert "Cost budget limit reached" in agent.state.error_message


@pytest.mark.asyncio
async def test_human_in_the_loop_approval():
    req = AgentRunRequest(prompt="Update user quota in production database with sensitive record")
    agent = SampleMonitoredAgent(req, "test_run_hitl")

    task = asyncio.create_task(agent.execute())

    # Wait until it enters WAITING_APPROVAL
    while agent.state.status != AgentRunStatus.WAITING_APPROVAL:
        await asyncio.sleep(0.05)

    assert agent.state.pending_approval is not None
    assert agent.state.pending_approval.tool_name == "execute_database_update"

    # Admin approves
    registry.resolve_approval("test_run_hitl", ApprovalDecision(approved=True, user="admin_alice"))

    await task
    assert agent.state.status == AgentRunStatus.COMPLETED
    assert "Successfully verified record and updated quota" in agent.state.final_output


@pytest.mark.asyncio
async def test_emergency_kill_switch():
    req = AgentRunRequest(prompt="Search knowledge base and calculate system latency metrics")
    agent = SampleMonitoredAgent(req, "test_run_kill")

    task = asyncio.create_task(agent.execute())
    await asyncio.sleep(0.2)

    # Operator triggers kill switch
    registry.request_kill("test_run_kill")

    await task
    assert agent.state.status == AgentRunStatus.KILLED
    assert "operator kill switch" in agent.state.error_message



def test_safety_benchmark_suite():
    from evals.run_benchmark import run_benchmark
    summary = run_benchmark()
    assert summary['total_scenarios'] == 25
    assert summary['accuracy_pct'] == 100.0
    assert summary['false_positive_rate_pct'] == 0.0
    assert summary['guardrails']['loop_detector']['recall_pct'] == 100.0
    assert summary['guardrails']['hitl_approval']['recall_pct'] == 100.0
    assert summary['guardrails']['budget_enforcement']['recall_pct'] == 100.0
