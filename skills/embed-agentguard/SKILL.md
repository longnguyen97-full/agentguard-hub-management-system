---
name: embed-agentguard
description: Automatically inspects any AI Agent project (Python or TypeScript/Node.js) and embeds AgentGuard monitoring, guardrails, and telemetry without breaking existing functionality. Supports both English and Vietnamese users.
---

# AgentGuard Embedder Skill

When the user requests to monitor, protect, or embed AgentGuard into their AI Agent or codebase:

## 1. Bilingual Communication Rule
- Detect the user's language from their prompt.
- If the user communicates in Vietnamese, explain actions and provide final summaries in **Vietnamese**.
- If the user communicates in English, respond in **English**.

## 2. Inspect Codebase & Detect Runtime
Scan the target workspace to identify:
- **Language**: Python (`requirements.txt`, `pyproject.toml`, `.py` files) or TypeScript/JavaScript (`package.json`, `.ts`, `.js` files).
- **Framework**: LangChain, CrewAI, AutoGen, LlamaIndex, Next.js API Routes, or vanilla agent loops.
- **Entrypoints**: Locate the core reasoning loop, tool execution dispatcher, or API handlers.

## 3. Inject Client SDK & Environment
- **For Python**:
  - Ensure `agent_sdk.py` is present in the project (copy from AgentGuard template if missing).
  - Add `AGENT_HUB_URL=http://localhost:8000` to `.env` (fallback: `http://localhost:8000`).
- **For TypeScript / Node.js**:
  - Ensure `agentHubClient.ts` is placed in `src/lib/` or `utils/`.
  - Add `AGENT_HUB_URL=http://localhost:8000` to `.env`.

## 4. Non-Invasive Instrumentation (Fail-Open Safety)
Wrap existing execution steps following the 3-phase lifecycle:
1. **Start of Task**: Call `start_run(agent_name, prompt, budget_usd, max_steps)` to obtain a `run_id`.
2. **Intermediate Steps / Tool Calls**: Call `log_step(...)` before/after each tool execution:
   - Mark `is_billable: true` for LLM generation/reasoning calls.
   - Mark `is_billable: false` ($0.00 / 0 tokens) for deterministic local computations (regex, DB queries, local formatting).
3. **Finish / Error**: Call `finish(final_output)` on success or `fail(error)` in catch blocks.
4. **Zero Downtime Guarantee (Fail-Open)**: Always wrap AgentGuard network calls inside `try...catch` / non-blocking handlers so that if AgentGuard Hub is temporarily offline, the user's agent continues to function without error.

## 5. Verification & Summary
1. Send a lightweight ping to `http://localhost:8000/health` to verify Hub connectivity.
2. Present the user with:
   - A clear summary of files created or modified.
   - A clickable link to the AgentGuard Live Dashboard: `http://localhost:8000/dashboard` (Live Mode).
   - A quick confirmation that their agent is now guarded against infinite loops, runaway costs, and sensitive unauthorized actions.
