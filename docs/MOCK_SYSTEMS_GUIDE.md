# COMPREHENSIVE GUIDE: SETUP, TESTING & METRIC INTERPRETATION WITH SATELLITE MOCK SYSTEMS
> **Language / Ngôn ngữ**: [English](MOCK_SYSTEMS_GUIDE.md) • [Tiếng Việt](MOCK_SYSTEMS_GUIDE.vi.md)  
> **Audience**: Developers, QA Engineers, and AI System Architects evaluating AgentGuard's control plane, safety guardrails, and telemetry across realistic enterprise AI agents.

---

## 1. Overview & Satellite Architecture

Unlike typical observability tools that only provide in-memory dummy stubs, **AgentGuard** includes a **cluster of 3 independent standalone host systems** (`mock-systems/`). Each service represents a standard enterprise workload, runs on a distinct technology stack (Python FastAPI, Node.js, and Python Worker), and directly embeds the **AgentGuard Sentinel SDK** to stream real-time telemetry and accept control interventions from the Hub:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                 3 STANDALONE SATELLITE AGENT SYSTEMS (MOCK-SYSTEMS)             │
├────────────────────────┬────────────────────────────────┬───────────────────────┤
│  1. E-Commerce Server  │       2. Fintech Service       │   3. Crawler Worker   │
│   (:8010 - FastAPI)    │       (:8020 - Node.js)        │     (:8030 - Python)  │
│ - Customer care & orders│ - Money transfers & bills     │ - Web & forum scraper │
│ - 100% Compliant Flow  │ - Human-in-the-Loop (HITL)     │ - Loop & Budget halts │
└───────────┬────────────┴────────────────┬───────────────┴───────────┬───────────┘
            │                             │                           │
            │ (agent_sdk.py)              │ (agentHubClient.js)       │ (agent_sdk.py)
            ▼                             ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      AGENTGUARD CONTROL PLANE & HUB (:8000)                     │
│                                                                                 │
│  [Live Sessions]  ──  [Loop Guardrail]  ──  [HITL Paused]  ──  [Kill Switch]    │
│            │                                                          │         │
│            ▼ (OTel Traces)                                            ▼ (SSE)   │
│   ┌─────────────────────┐                                   ┌─────────────────┐ │
│   │ Langfuse Core :3000 │                                   │ Dashboard :8000 │ │
│   │ (ClickHouse & PG)   │                                   │ (Live Mode UI)  │ │
│   └─────────────────────┘                                   └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Environment Setup & Prerequisites

### Prerequisites:
- **Python 3.10+** (fast package manager `uv` recommended).
- **Node.js 18+** (required to run Satellite Service 2: Fintech Service).
- **Docker & Docker Compose** (recommended for self-hosted Langfuse & ClickHouse cluster).

### 3-Step Infrastructure Launch:

#### Step 1: Start Langfuse Observability Cluster
From the root workspace directory:
```bash
docker compose up -d
```
> Verify access at `http://localhost:3000` (`admin@example.com` / `AdminPassword123!`).

#### Step 2: Start AgentGuard Control Hub (:8000)
Open a new Terminal window:
```bash
uv run run.py
```
Or directly with uvicorn:
```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

#### Step 3: Verify Hub Health Check
Open your browser or run:
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "service": "AgentGuard Control Plane",
  "active_runs": 0
}
```

---

## 3. Three Testing Methods for Mock Systems

### Method A (Recommended): 1-Command Automated Test Suite (All-in-One Orchestrator)
This is the fastest, completely automated way to run an end-to-end verification:
```bash
uv run python mock-systems/run_all.py --test
```
**Automated Execution Pipeline:**
1. Spawns all 3 satellite servers (`:8010`, `:8020`, `:8030`) in background processes.
2. Waits 3.5 seconds for network ports to be fully ready and listening.
3. Automatically dispatches realistic operational payloads to each service:
   - Order tracking and coupon generation inquiry to E-Commerce (`:8010`).
   - High-value electric bill payment transfer to Fintech (`:8020`).
   - Infinite recursive pagination loop crawl to Crawler (`:8030`).
4. Streams reasoning steps, token metrics, costs, and guardrail alerts live to Hub (`:8000`).
5. Safely tears down background processes and releases network ports upon completion.

---

### Method B: Persistent Daemon Mode (For Interactive cURL / Postman Exploration)
Keep all 3 services running continuously in the background so you can dispatch custom requests manually:
```bash
uv run python mock-systems/run_all.py --daemon
```
> Press `Ctrl + C` in the terminal when you are ready to terminate all services.

---

### Method C: Launch Individual Services Standalone
If you prefer observing individual terminal console logs:

#### 1. E-Commerce Customer Care Service (:8010)
```bash
cd mock-systems/ecommerce-service
uv run python app.py
```

#### 2. Fintech & E-Wallet Service (:8020 - Node.js)
```bash
cd mock-systems/fintech-service
node server.js
```

#### 3. Autonomous Web Crawler Worker (:8030)
```bash
cd mock-systems/crawler-worker
uv run python worker.py
```

---

## 4. Business Roles & Guardrail Verification Across Satellite Systems

### 🛍️ System 1: E-Commerce Customer Care (:8010 - FastAPI)
- **Business Persona**: Autonomous customer support agent answering order inquiries from an internal SQLite database and issuing apology discount coupons for delayed shipments.
- **Tested Guardrail**: **100% Compliant Flow & Cost Separation**.
- **Technical Highlights**:
  - *Billable LLM Reasoning*: Marked `is_billable: True`, tracks OpenAI/Anthropic model token fees accurately.
  - *Deterministic Local Database Queries*: Marked `is_billable: False`, tagged with **Deterministic (Free / $0.00)** and 0 tokens so internal compute never skews AI financial audits.
- **Manual cURL Verification**:
  ```bash
  curl -X POST http://localhost:8010/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Where is my order DH-1002?", "order_id": "DH-1002"}'
  ```

---

### 💳 System 2: Fintech & E-Wallet Service (:8020 - Node.js)
- **Business Persona**: Autonomous AI financial assistant parsing monthly bills and executing bank payments on behalf of users.
- **Tested Guardrail**: **Human-in-the-Loop Approval (HITL)**.
- **Technical Highlights**:
  - After bill parsing, when the agent attempts sensitive financial mutation tool `execute_bank_transfer` ($100.00 / 2,500,000 VND), the Sentinel SDK halts execution and signals the Hub.
  - The Node.js execution loop automatically **pauses** in state `WAITING_APPROVAL`.
  - On the AgentGuard Dashboard, an orange approval prompt appears with two actions: **Authorize** and **Reject**.
  - Execution thread only resumes and dispatches funds after explicit human operator confirmation.
- **Manual cURL Verification**:
  ```bash
  curl -X POST http://localhost:8020/api/transfer \
    -H "Content-Type: application/json" \
    -d '{"account_id": "ACC-9988", "recipient": "EVN-ELECTRIC", "amount": 2500000}'
  ```

---

### 🕷️ System 3: Autonomous Crawler Worker (:8030 - Python Worker)
- **Business Persona**: Automated data pipeline crawler scraping stock market financial disclosures and community forums.
- **Tested Guardrail**: **Infinite Loop Detector** & **Hard Budget Guardrail**.
- **Technical Highlights**:
  - Encounters a recursive redirect trap between pagination URLs (`page=1` <-> `page=2`).
  - Calls `fetch_page` repeatedly with identical argument hashes.
  - On the 2nd consecutive repetition, AgentGuard's **Deterministic Tool Hash Interceptor** aborts execution immediately with status `TERMINATED_LOOP`, saving API balances from infinite token burn.
- **Manual cURL Verification**:
  ```bash
  curl -X POST http://localhost:8030/api/crawl/loop
  ```

---

## 5. Step-by-Step Metric Interpretation on Dashboard (:8000/dashboard)

Open your browser to:
👉 **`http://localhost:8000/dashboard`**

### ⚠️ Essential Prerequisite: Toggle to "Live Mode: ON"
- **Simulation Mode (Yellow)**: Sandbox environment running preset mock scenarios from local memory.
- **Live Mode (Green)**: Ingests live production and external agent runs (`mock-systems/` or your own deployed agents).
> *When testing mock systems, make sure the top-right toggle displays:* **`Live Mode: ON`**.

---

### 📊 1. Header KPI Cards Overview

| Metric Card | Technical Meaning | Real-World Operational Interpretation |
| :--- | :--- | :--- |
| **Total Runs (Tổng Số Phiên Chạy)** | Total independent operational sessions registered with the Hub via Sentinel SDK. | Each customer inquiry, financial transfer, or web scraping task counts as 1 distinct Run with multiple reasoning steps. |
| **Pending Approval (Đang Chờ Phê Duyệt)** | Sensitive actions currently frozen awaiting human authorization. | When running Fintech (:8020), this increments to **1** (orange badge). Click the session card to authorize or reject. |
| **Total Tokens (Tổng Token Ghi Nhận)** | Aggregate billable tokens consumed by ReAct reasoning steps. | Only sums tokens where `is_billable: True`. Deterministic database queries and local helpers consume 0 tokens. |
| **Estimated Cost (Ước Tính Chi Phí)** | Live calculated financial cost, switchable between **USD ($)** and **VND (₫)**. | Computed against official model pricing (e.g. GPT-4o-mini: \$0.15/M input, \$0.60/M output). Click the currency button to toggle. |

---

### 🔍 2. Step Trajectory & ReAct Reasoning Inspector

Select any session from the left column (e.g., `run_...` from `FintechAccountAgent` or `CustomerCareAgent`). The right pane displays the complete execution tree:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ↳ Step 1                                            180ms  245 tokens │
├────────────────────────────────────────────────────────────────────────┤
│ 🧠 LLM Reasoning (Billable API Token Generation):             $0.0001 │
│ "Received request to transfer 2,500,000 VND for EVN. Checking balance  │
│  for user account ACC-9988."                                           │
├────────────────────────────────────────────────────────────────────────┤
│ 🛠️ Tool Call: check_account_balance        ⚡ Deterministic (Free / $0) │
│ Parameters: {"account_id": "ACC-9988"}                                 │
│ Result:     {"balance_vnd": 15400000, "status": "active"}             │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Reasoning Step (`🧠 LLM Reasoning`)**:
   - Displays the agent's internal planning thought before selecting an action.
   - Shows token count (e.g. `245 tokens`) and calculated cost (`$0.0001`).
2. **Tool Execution (`🛠️ Tool Call`)**:
   - Displays the invoked tool name (`check_account_balance`, `query_database`, `fetch_page`).
   - Green badge **`⚡ Deterministic (Free / $0.00)`**: Confirms local computation with $0.00 cost.
3. **Parameters & Result**:
   - JSON payloads inspectable with exact inputs and outputs.
4. **Human-in-the-Loop Approval Banner**:
   - Provides green **`Authorize`** and red **`Reject`** buttons for paused runs.
5. **Emergency Kill Switch**:
   - Red button at the top-right allows operators to instantly terminate misbehaving runs.

---

### 📈 3. Deep Traces on Langfuse Core (:3000)

All spans, generations, and token analytics are asynchronously synced to ClickHouse:
- Visit: **`http://localhost:3000`**
- Inspect:
  - Span Waterfall waterfall diagrams down to the microsecond level.
  - Raw prompt and completion inputs/outputs.
  - p95 and p99 latency distributions across all connected agent clusters.

---

## 6. Troubleshooting Common Issues

1. **Port Already in Use (`Port 8010/8020/8030 already in use`)**:
   - Terminate lingering processes:
     - Windows PowerShell: `Stop-Process -Name node, python -Force`
     - Linux/macOS: `fuser -k 8010/tcp 8020/tcp 8030/tcp`
2. **Runs Not Showing on Dashboard**:
   - Ensure the toggle at the top of `/dashboard` is set to **`Live Mode: ON`**.
3. **Vietnamese Console Encoding on Windows**:
   - AgentGuard automatically forces UTF-8 in Python. In PowerShell, you can run `chcp 65001`.

---

## 💖 7. Community, Feedback & Sponsorship (Donate)

We welcome your feedback, issues, and ideas:
- **⭐ Star on GitHub**: [GitHub Repository](https://github.com/longnguyen97-full/agentguard-hub-management-system/)
- **💬 Bug Reports & Guardrail Proposals**: [GitHub Issues](https://github.com/longnguyen97-full/agentguard-hub-management-system/issues)

### ☕ Support the Author (Buy Me a Coffee)
If you find **AgentGuard** valuable for securing your AI agents, consider supporting our ongoing open-source work:

<div align="center">
  <img src="https://i.postimg.cc/Zqg3GGpG/qrcode.jpg" alt="AgentGuard Donation QR Code" width="220" style="border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
  <br/>
  <em>Scan via Mobile Banking / VietQR to support this project</em>
  <br/>
  <strong>Thank you for empowering open-source AI safety! ❤️</strong>
</div>
