/**
 * AgentGuard Sentinel Client for Node.js / JavaScript
 */

const HUB_URL = process.env.AGENT_HUB_URL || 'http://localhost:8000';

class AgentSentinelNode {
  constructor(endpoint = HUB_URL) {
    this.endpoint = endpoint.replace(/\/$/, '');
  }

  async startRun({ agentName, prompt, maxSteps = 5, budgetUsd = 0.50, userId = 'fintech_user' }) {
    try {
      const res = await fetch(`${this.endpoint}/api/agents/external/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_name: agentName,
          prompt,
          max_steps: maxSteps,
          budget_usd: budgetUsd,
          user_id: userId,
        }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      return new AgentSessionNode(this, data.run_id, agentName);
    } catch (err) {
      console.warn('[AgentGuard Sentinel] startRun offline:', err.message);
      return null;
    }
  }
}

class AgentSessionNode {
  constructor(tracker, runId, agentName) {
    this.tracker = tracker;
    this.runId = runId;
    this.agentName = agentName;
    this.stepCount = 0;
  }

  async logStep({ thought, toolName = null, toolInput = {}, toolOutput = null, tokensUsed = 0, costUsd = 0, latencyMs = 120, isBillable = true }) {
    this.stepCount += 1;
    try {
      const res = await fetch(`${this.tracker.endpoint}/api/agents/external/${this.runId}/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          step_number: this.stepCount,
          thought,
          action_type: toolName ? 'tool_call' : 'reasoning',
          tool_name: toolName,
          tool_input: toolInput,
          tool_output: toolOutput,
          tokens_used: tokensUsed,
          cost_usd: costUsd,
          latency_ms: latencyMs,
          is_billable: isBillable,
        }),
      });
      return res.ok;
    } catch (err) {
      console.warn('[AgentGuard Sentinel] logStep offline:', err.message);
      return false;
    }
  }

  async finish(finalOutput) {
    try {
      await fetch(`${this.tracker.endpoint}/api/agents/external/${this.runId}/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'COMPLETED', final_output: finalOutput }),
      });
    } catch (err) {
      // fail-open
    }
  }

  async fail(errorMsg) {
    try {
      await fetch(`${this.tracker.endpoint}/api/agents/external/${this.runId}/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'FAILED', error: errorMsg }),
      });
    } catch (err) {
      // fail-open
    }
  }
}

module.exports = { AgentSentinelNode };
