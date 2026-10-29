# HƯỚNG DẪN TÍCH HỢP HỆ THỐNG GIÁM SÁT & QUẢN TRỊ AI AGENT (AGENTGUARD)
> **Dành cho**: Developer / Kỹ sư AI phát triển các hệ thống Agent độc lập (Python, Node.js, Next.js, Go) muốn kết nối vào AgentGuard Hub.

---

## 1. Giới Thiệu & Kiến Trúc 2 Tầng (Two-Tier Architecture)

<div align="center">
  <img src="../assets/agent-hub-architecture.svg" alt="Sơ Đồ Nguyên Lý Hoạt Động AgentGuard Hub" width="100%" />
</div>

AgentGuard kết hợp 2 tầng giám sát độc lập nhưng bổ trợ lẫn nhau:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ỨNG DỤNG BÊN NGOÀI (EXTERNAL CLIENT)                  │
│       (Ví dụ: Hệ thống sửa kịch bản Content Moderator, Customer Care Agent, ...)    │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │ (1) Telemetry / Traces        │ (2) Live Session Ingestion
                       │ (OpenInference / OTel)        │ (Vòng đời & Điều khiển)
                       ▼                               ▼
       ┌───────────────────────────────┐ ┌───────────────────────────────────┐
       │     LANGFUSE OBSERVABILITY    │ │      AGENTGUARD CONTROL PLANE     │
       │           (:3000)             │ │              (:8000)              │
       │ - Tracing chi tiết (Tree)     │ │ - Bảng Live Agent Sessions        │
       │ - Đo đếm Token & Chi phí      │ │ - Emergency Kill Switch           │
       │ - Lưu trữ ClickHouse / PG     │ │ - Loop & Budget Guardrails        │
       │ - Evals & Dataset             │ │ - Human-in-the-Loop Approval      │
       └───────────────┬───────────────┘ └─────────────────┬─────────────────┘
                       │                                   │
                       └───────────────►◄──────────────────┘
                            (ClickHouse Query Telemetry)
```

### ⚠️ Lưu ý quan trọng về "Live Agent Sessions" vs "Langfuse Traces":
- **Langfuse (:3000)**: Lưu trữ lịch sử toàn bộ các **Traces**, **Spans** (đoạn 0đ) và **Generations** (đoạn tốn token) từ trước đến nay.
- **AgentGuard Dashboard (:8000/dashboard)**:
  - Khi bật **Simulation Mode**: Hiển thị các kịch bản chạy thử nghiệm mẫu có sẵn.
  - Khi bật **Live Mode**: Hiển thị danh sách **Live Agent Sessions** được đăng ký qua Hub API (`/api/agents/external/...`). Nếu Client chỉ mới nhúng Langfuse SDK mà chưa gọi API đăng ký phiên vào Hub `:8000`, mục này sẽ hiển thị:  
    *`"No live external agent runs yet. Ingest via SDK or check Langfuse traces at :3000!"`* (kèm nút xem nhanh số Traces tích lũy trong ClickHouse).

---

## 2. Phương Án 0 (Khuyến Nghị Tuyệt Đối): Tích Hợp Tự Động Bằng Trợ Lý AI Coding

> **Dành cho**: Developer sử dụng **Google Antigravity**, **Cursor**, **Claude Code**, **GitHub Copilot Workspace**, hoặc **Windsurf**.  
> **Ưu điểm**: Bạn **không cần phải tự tay copy/paste mã hay sửa thủ công từng file**. Trợ lý AI sẽ đọc tài liệu kỹ thuật và bộ quy chuẩn chuẩn hóa của AgentGuard để nhúng chốt chặn vào hệ thống của bạn chỉ với **1 câu lệnh duy nhất**.

### 🌟 Bộ AI Skill Chuẩn Hóa: `skills/embed-agentguard/SKILL.md`

AgentGuard cung cấp sẵn một AI Skill được tối ưu hóa theo quy chuẩn Agentic Coding tại:
👉 [`skills/embed-agentguard/SKILL.md`](../skills/embed-agentguard/SKILL.md)

### 🚀 Câu Lệnh Kích Hoạt (Prompt Mẫu)

Mở cửa sổ Chat với Trợ lý AI của bạn (Antigravity / Cursor / Claude Code) và nhập:

#### Tiếng Việt:
```text
Hãy đọc file skills/embed-agentguard/SKILL.md và tự động nhúng toàn bộ chốt chặn giám sát AgentGuard vào project agent này (kết nối về Hub tại http://localhost:8000). Đảm bảo giữ nguyên logic hiện tại và áp dụng cơ chế an toàn fail-open.
```

#### English:
```text
Read skills/embed-agentguard/SKILL.md and embed AgentGuard monitoring, safety guardrails, and telemetry into this AI agent project (connecting to Hub at http://localhost:8000). Ensure zero-downtime fail-open safety.
```

### ⚙️ Quy Trình 6 Bước Mà Trợ Lý AI Sẽ Tự Thực Hiện:

```mermaid
flowchart TD
    A["1. Quét Kiến Trúc Dự Án<br/>(Python / TypeScript / Framework)"] --> B["2. Tự Động Chép Sentinel SDK<br/>(agent_sdk.py hoặc agentHubClient.ts)"]
    B --> C["3. Nhúng Biến Môi Trường<br/>AGENT_HUB_URL=http://localhost:8000 vào .env"]
    C --> D["4. Bọc Vòng Lặp Suy Luận Với Cơ Chế Fail-Open<br/>(start_run -> log_step -> finish/fail)"]
    D --> E["5. Tách Biệt Chi Phí API vs Công Cụ 0₫<br/>(is_billable: true / false)"]
    E --> F["6. Ping Kiểm Tra /health & Cung Cấp Link Dashboard"]
```

1. **Nhận diện Runtime & Framework**: Tự động phát hiện dự án dùng Python (LangChain, CrewAI, AutoGen, LlamaIndex, script thuần) hay Node.js/TypeScript (Next.js App Router, Express, NestJS).
2. **Cung cấp Client Helper tương thích**:
   - Dự án Python: Tạo hoặc chép `agent_sdk.py`.
   - Dự án TypeScript: Tạo `src/lib/agentHubClient.ts`.
3. **Cấu hình biến môi trường**: Tự động bổ sung `AGENT_HUB_URL=http://localhost:8000` vào `.env`.
4. **Bọc chốt chặn an toàn với nguyên lý Fail-Open (Zero Downtime)**:
   - Toàn bộ lệnh gọi tới AgentGuard Hub được bảo vệ trong khối `try...except` / `try...catch` không đồng bộ.
   - Nếu AgentGuard Hub tắt hoặc bảo trì, **agent của bạn vẫn chạy hoàn toàn bình thường**, không bao giờ bị dừng ngoài ý muốn!
5. **Định danh chi phí chuẩn xác ($0.00 vs API Tokens)**:
   - Các bước suy luận LLM (OpenAI, Claude, Gemini) được đánh dấu `is_billable: true` kèm số token và chi phí.
   - Các công cụ tất định nội bộ (Regex check, query SQL, format dữ liệu) được đánh dấu `is_billable: false` ($0.00 / 0 token) để không làm sai lệch báo cáo chi phí.
6. **Kiểm thử & Bàn giao**: Gửi tín hiệu kiểm tra tới `http://localhost:8000/health` và cung cấp link mở Dashboard trực tiếp: `http://localhost:8000/dashboard`.

---

## 3. Phương Án 1: Tích Hợp Thủ Công Cho Node.js / TypeScript / Next.js

Dành cho các ứng dụng web fullstack (như Next.js, Express, NestJS).

### Bước 1: Tạo Helper Client `agentHubClient.ts`
Tạo file `src/lib/agentHubClient.ts` trong dự án của bạn:

```typescript
const HUB_ENDPOINT = process.env.AGENT_HUB_URL || 'http://localhost:8000';

export interface ExternalRunStartParams {
  agent_name: string;
  prompt: string;
  max_steps?: number;
  budget_usd?: number;
  user_id?: string;
  model?: string;
}

export interface ExternalStepLogParams {
  step_number: number;
  thought: string;
  action_type?: 'reasoning' | 'tool_call' | 'approval_request';
  tool_name?: string | null;
  tool_input?: any;
  tool_output?: any;
  tokens_used?: number;
  cost_usd?: number;
  latency_ms?: number;
  is_billable?: boolean;
}

export interface ExternalRunFinishParams {
  status: 'COMPLETED' | 'FAILED';
  final_output?: string | null;
  error?: string | null;
}

// 1. Đăng ký phiên chạy mới vào Hub
export async function startAgentRun(params: ExternalRunStartParams) {
  try {
    const res = await fetch(`${HUB_ENDPOINT}/api/agents/external/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_name: params.agent_name,
        prompt: params.prompt,
        max_steps: params.max_steps || 10,
        budget_usd: params.budget_usd || 0.50,
        user_id: params.user_id || 'external_user',
        model: params.model || 'gemini-2.5-flash',
      }),
    });
    if (!res.ok) return null;
    return await res.json(); // { run_id: "ext_xxx", ... }
  } catch (err) {
    console.warn('[AgentGuard] Start failed:', err);
    return null;
  }
}

// 2. Ghi nhận từng bước (bước tốn token hoặc bước công cụ tất định 0đ)
export async function logAgentStep(run_id: string, step: ExternalStepLogParams) {
  if (!run_id) return false;
  try {
    const res = await fetch(`${HUB_ENDPOINT}/api/agents/external/${run_id}/step`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(step),
    });
    return res.ok;
  } catch (err) {
    console.warn('[AgentGuard] Step log error:', err);
    return false;
  }
}

// 3. Báo cáo hoàn tất hoặc thất bại
export async function finishAgentRun(run_id: string, params: ExternalRunFinishParams) {
  if (!run_id) return false;
  try {
    const res = await fetch(`${HUB_ENDPOINT}/api/agents/external/${run_id}/finish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return res.ok;
  } catch (err) {
    console.warn('[AgentGuard] Finish error:', err);
    return false;
  }
}
```

### Bước 2: Gọi trong API Route (Ví dụ API Sửa kịch bản / Phân tích kịch bản)

```typescript
import { startAgentRun, logAgentStep, finishAgentRun } from '@/lib/agentHubClient';

export async function POST(req: Request) {
  const { text, platform } = await req.json();

  // 1. Khởi tạo phiên chạy trên AgentGuard Live Sessions
  const session = await startAgentRun({
    agent_name: 'External_Content_Moderator',
    prompt: `[${platform}] ${text.slice(0, 100)}`,
    budget_usd: 0.20,
    max_steps: 3,
  });

  // 2. Bước 1: Quét từ khóa tất định (MIỄN PHÍ 0đ / 0 token)
  const regexResult = localRegexScan(text);
  if (session) {
    await logAgentStep(session.run_id, {
      step_number: 1,
      thought: 'Chạy bộ quét Regex từ cấm tất định nội bộ (0đ).',
      tool_name: 'regex_policy_scanner',
      tool_input: { textLength: text.length },
      tool_output: { matches: regexResult.length },
      tokens_used: 0,
      cost_usd: 0,
      is_billable: false,
    });
  }

  // 3. Bước 2: Gọi LLM tối ưu nội dung (CÓ TÍNH PHÍ API TOKEN)
  const llmRes = await callGeminiApi(text);
  if (session) {
    await logAgentStep(session.run_id, {
      step_number: 2,
      thought: 'Gọi LLM Gemini viết lại nội dung sạch từ vi phạm chính sách.',
      tool_name: 'gemini_content_rewrite',
      tokens_used: llmRes.tokens,
      cost_usd: llmRes.costUsd,
      is_billable: true,
    });
  }

  // 4. Kết thúc phiên chạy
  if (session) {
    await finishAgentRun(session.run_id, {
      status: 'COMPLETED',
      final_output: llmRes.rewrittenText,
    });
  }

  return Response.json({ success: true, result: llmRes.rewrittenText });
}
```

---

## 3. Phương Án 2: Tích Hợp Cho Python (Sử dụng `agent_sdk.py`)

Nếu Agent của bạn viết bằng Python (LangChain, AutoGen, CrewAI hoặc Python script):

```python
from agent_sdk import AgentTracker

# 1. Khởi tạo tracker
tracker = AgentTracker(endpoint="http://localhost:8000")

# 2. Bắt đầu một phiên làm việc của Agent
session = tracker.start_run(
    agent_name="ECommerceSupportAgent",
    prompt="Hỗ trợ xử lý khiếu nại hoàn tiền đơn hàng #ORD-8821",
    budget_usd=0.20,
    max_steps=5
)
print(f"Phiên đang chạy với Run ID: {session.run_id}")

# 3. Ghi nhận bước tốn phí LLM Reasoning
session.log_step(
    thought="Khách hàng yêu cầu hoàn tiền. Cần kiểm tra lịch sử giao dịch.",
    tool_name="order_database_query",
    tool_input={"order_id": "ORD-8821"},
    tool_output={"status": "DELIVERED", "eligible_for_refund": True},
    tokens_used=180,
    cost_usd=0.00005,
    is_billable=True
)

# 4. Ghi nhận bước tất định (Miễn phí 0đ)
session.log_step(
    thought="Tạo mã voucher đền bù 20% qua hệ thống mã nội bộ.",
    tool_name="create_compensation_voucher",
    tool_input={"discount": 20},
    tool_output={"code": "REFUND20"},
    tokens_used=0,
    cost_usd=0.0,
    is_billable=False
)

# 5. Hoàn tất
session.finish(final_output="Đã xử lý hoàn tiền và cấp mã REFUND20.")
```

---

## 4. Chi Tiết Các REST Endpoints Cho Live Agent Sessions

Tất cả các hệ thống bên ngoài có thể giao tiếp trực tiếp qua REST API tại `http://localhost:8000`:

### `POST /api/agents/external/start`
Khởi tạo phiên chạy và đăng ký vào bảng quản trị trực tiếp.
- **Request Body**:
  ```json
  {
    "agent_name": "Tên Agent của bạn",
    "prompt": "Mô tả tác vụ đầu vào",
    "max_steps": 10,
    "budget_usd": 0.50,
    "user_id": "user_id_hoac_creator_id",
    "model": "gemini-2.5-flash"
  }
  ```
- **Response**:
  ```json
  {
    "run_id": "ext_4985b80096",
    "status": "RUNNING",
    "agent_name": "...",
    "created_at": "..."
  }
  ```

### `POST /api/agents/external/{run_id}/step`
Gửi thông tin bước suy luận hoặc gọi tool. Dữ liệu này sẽ được phát realtime qua Server-Sent Events (SSE) lên Dashboard.
- **Request Body**:
  ```json
  {
    "step_number": 1,
    "thought": "Suy nghĩ hoặc mô tả hành động",
    "action_type": "tool_call",
    "tool_name": "tên_công_cụ",
    "tool_input": { "key": "value" },
    "tool_output": { "result": "..." },
    "tokens_used": 240,
    "cost_usd": 0.00008,
    "latency_ms": 120.0,
    "is_billable": true
  }
  ```

### `POST /api/agents/external/{run_id}/finish`
Đánh dấu kết thúc phiên chạy.
- **Request Body**:
  ```json
  {
    "status": "COMPLETED",
    "final_output": "Nội dung trả về hoàn chỉnh cho người dùng"
  }
  ```
  *(Hoặc `status: "FAILED"`, `"error": "thông tin lỗi"` nếu gặp sự cố)*

---

## 5. Bảng Phân Định Chi Phí: Đoạn Tốn Phí vs Đoạn Miễn Phí

| Loại Thao Tác | Bản Chất | Tốn Phí Không? | Ghi chú Telemetry |
| :--- | :--- | :--- | :--- |
| **LLM Call (GPT-4o, Claude, Gemini)** | Suy luận xác suất (Probabilistic Reasoning) | 💸 **CÓ TỐN PHÍ** | `is_billable: true`, ghi nhận Tokens, USD/VND |
| **Local Tool / Code Regex thuần** | Xử lý tất định (Deterministic Logic) | ⚡ **MIỄN PHÍ (0đ)** | `is_billable: false`, cost = 0, chỉ đo Latency |
| **Truy vấn SQL / Vector DB nội bộ** | Truy xuất dữ liệu (Data Retrieval) | ⚡ **MIỄN PHÍ (0đ)** | `is_billable: false`, cost = 0 |
| **External Paid API (SerpAPI, Twilio)** | Dịch vụ trả phí bên ngoài | 💸 **CÓ TỐN PHÍ** | Ghi nhận chi phí theo cước nhà cung cấp |

---

## 6. Hướng Dẫn Sử Dụng Dashboard AgentGuard (:8000/dashboard)

1. Mở trình duyệt tại: **`http://localhost:8000/dashboard`**.
2. **Gạt công tắc chế độ**:
   - Gạt sang **Live Mode** để theo dõi các Agent thực tế từ bên ngoài (như Content Reviewer, Sales Bot).
   - Gạt sang **Simulation Mode** nếu muốn bấm thử các kịch bản mẫu (Kill Switch, Human Approval, Loop Trap).
3. **Quan sát Live Sessions**:
   - Khi có request từ Agent bên ngoài gửi qua SDK, phiên chạy sẽ lập tức xuất hiện trong cột **Agent Sessions**.
   - Bấm vào phiên chạy để xem chi tiết Timeline từng bước, tỷ lệ tốn phí (USD/VND) và link xem Trace chuyên sâu trên Langfuse (:3000).

---

## 7. Các Lưu Ý Sống Còn Khi Tích Hợp (Crucial Notes & Troubleshooting)

### 🔴 Lưu Ý 1: Xử Lý Tiếng Việt (UTF-8) Trên Windows (Tránh lỗi `?` và hình thoi ``)
Nếu Agent của bạn chạy trên **Windows** và gửi nội dung tiếng Việt có dấu (`[TIKTOK] Mỹ phẩm trị mụn số 1 Việt Nam...`), bạn rất dễ gặp tình trạng các ký tự bị biến thành dấu hỏi `M? ph?m tr? m?n...` do bảng mã mặc định của Windows là `cp1252 / ANSI`.

* **Khắc phục trong Python Client:**
  Thêm 2 dòng này ở **dòng đầu tiên** của script client:
  ```python
  import os
  os.environ["PYTHONUTF8"] = "1"
  ```
  Khi mở file văn bản, **bắt buộc** truyền `encoding="utf-8"`:
  ```python
  # ĐÚNG:
  with open("prompt.txt", "r", encoding="utf-8") as f:
      text = f.read()
  ```
* **Khắc phục trong Node.js / Fetch / cURL:**
  Luôn đặt Header rõ ràng:
  ```javascript
  headers: {
    "Content-Type": "application/json; charset=utf-8"
  }
  ```
* **Khắc phục trên Terminal / PowerShell:**
  Gõ lệnh sau trước khi chạy script để chuyển console sang UTF-8:
  ```powershell
  chcp 65001
  ```

---

### 🟡 Lưu Ý 2: Tránh Lỗi `ModuleNotFoundError: No module named 'fastapi'`
* Khi chạy Hub quản trị, **không dùng** lệnh `python run.py` (vì có thể trỏ vào Python hệ điều hành chưa có thư viện).
* **Luôn sử dụng lệnh của `uv`**:
  ```bash
  uv run run.py
  # hoặc:
  uv run agent-hub
  ```
  `uv` sẽ tự động đảm bảo 100% môi trường và thư viện luôn sẵn sàng.

---

### 🟢 Lưu Ý 3: Phân Định Rạch Ròi Đoạn Tốn Phí (`is_billable: true`) vs Miễn Phí (`is_billable: false`)
* Chỉ đặt `is_billable: true` khi có **gọi đến LLM (OpenAI, Gemini, Claude)** hoặc **API trả phí bên thứ 3 (SerpAPI, Twilio)**.
* Các bước chạy **code Python thuần, Regex, quét từ cấm, tính toán công thức, query Database nội bộ**:
  * Đặt `is_billable: false`
  * Đặt `tokens_used: 0`
  * Đặt `cost_usd: 0.0`
  * Mục tiêu: Giữ cho báo cáo tài chính của doanh nghiệp không bị phóng đại sai lệch chi phí.

---

### 🔵 Lưu Ý 4: Quy Trình Phê Duyệt Của Con Người (Human-in-the-Loop)
* Khi khởi tạo Agent, nếu khai báo danh sách `require_approval_tools`:
  ```json
  "require_approval_tools": ["delete_database", "execute_payment", "send_mass_email"]
  ```
* Khi Agent chạm vào các tool này, Agent sẽ **tự động Pause** và chuyển sang trạng thái `WAITING_APPROVAL`.
* Người quản trị có thể duyệt qua Web Dashboard hoặc gọi API:
  `POST /api/agents/runs/{run_id}/approve` với `{"approved": true, "user": "admin"}`.

---

### 🟣 Lưu Ý 5: Thứ Tự Khởi Động Hệ Thống Chuẩn Production
1. **Bước 1 (Hạ tầng lưu trữ trace):**
   ```bash
   docker compose up -d
   ```
   *(Đợi 30 giây để Langfuse Web :3000 và Postgres/ClickHouse sẵn sàng)*
2. **Bước 2 (Hub quản trị & Dashboard):**
   ```bash
   uv run run.py
   ```
   *(Mở Dashboard tại `http://localhost:8000/dashboard`)*
3. **Bước 3 (Chạy các ứng dụng Client / Agent):**
   *(Ứng dụng ngoài gửi task hoặc telemetry về Hub :8000)*

---

### 🛡️ Lưu Ý 6: Thiết Lập Bảo Mật API Key
* Khi đưa vào môi trường Production hoặc mạng dùng chung, thiết lập biến môi trường `API_KEY` trong file `.env`:
  ```env
  API_KEY=ag_live_secret_key_prod_2026
  ```
* Sau khi thiết lập, mọi Client Agent phải truyền kèm header:
  ```http
  X-API-Key: ag_live_secret_key_prod_2026
  ```
  hoặc:
  ```http
  Authorization: Bearer ag_live_secret_key_prod_2026
  ```
* Trong Python SDK:
  ```python
  tracker = AgentTracker(endpoint="http://localhost:8000", api_key="ag_live_secret_key_prod_2026")
  ```
* Trong Dev Mode (`API_KEY` để trống/None), Hub cho phép truy cập mở không cần khóa.

---

### 📊 Lưu Ý 7: Xuất Báo Cáo Kiểm Toán Audit (CSV / JSON) & Replay
* **Xuất chi tiết 1 phiên chạy:**
  * JSON: `GET /api/agents/runs/{run_id}/export?format=json`
  * CSV: `GET /api/agents/runs/{run_id}/export?format=csv`
* **Xuất tổng hợp toàn bộ các phiên:**
  * CSV: `GET /api/agents/export/all`
* **Xem lại tư duy từng bước (Time-Travel Replay):**
  * Trên thanh Inspector, bấm `[Play]`, `[Next]`, hoặc `[Prev]` để tua lại hành trình suy luận của Agent qua từng bước.

---

### 🌐 Lưu Ý 8: Tích Hợp Chuẩn OpenTelemetry (OTLP) cho CrewAI, LangGraph, AutoGen
* AgentGuard cung cấp sẵn endpoint tiếp nhận chuẩn OpenTelemetry:
  * `POST http://localhost:8000/v1/traces`
  * `POST http://localhost:8000/api/otlp/v1/traces`
* Khi sử dụng framework có sẵn OTel (ví dụ: `opentelemetry-exporter-otlp` trong CrewAI, LangChain, AutoGen):
  ```bash
  export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:8000/v1/traces"
  export OTEL_EXPORTER_OTLP_PROTOCOL="http/json"
  ```
* Hệ thống sẽ tự động bóc tách các spans, tính toán token & chi phí thực, nhận diện tool call, và hiển thị trực tiếp lên AgentGuard Dashboard mà không cần can thiệp sâu vào code agent!

---

### 🔔 Lưu Ý 9: Cấu Hình Webhook Alerts Trên Giao Diện Dashboard
* Người dùng có thể bấm trực tiếp vào nút **Webhook Alerts** trên thanh tiêu đề của Dashboard.
* Hộp thoại cấu hình cho phép:
  * Nhập URL Webhook của Discord (tự động render Rich Embeds), Slack (Block Kit), hoặc n8n / Custom JSON.
  * Bấm nút **Send Test Alert** để gửi thử tin nhắn kiểm tra đường truyền trước khi lưu.
  * Lưu cấu hình động mà không cần khởi động lại máy chủ.

---

### 🔤 Lưu Ý 10: Cơ Chế Tự Động Khôi Phục Lỗi Font Tiếng Việt & Cách Tránh Ký Tự `?`
* **Cơ chế tự sửa lỗi trên Hub:**
  * AgentGuard đã tích hợp thư viện **`ftfy`** và chuẩn hóa Unicode (NFC). Mọi chuỗi bị lỗi mojibake dạng Latin-1 (như `MÃ¨o bÃ©o` -> `Mèo béo`) hoặc ký tự Unicode escaped (`\u1ef9` -> `ỹ`) đều được hệ thống tự động nhận diện và sửa sạch khi nhận payload.
* **Nguyên nhân xuất hiện dấu `?` (ASCII 63):**
  * Ký tự `?` xuất hiện khi **bản thân client gửi lên đã biến chữ có dấu thành dấu chấm hỏi** trước khi tới máy chủ.
  * Phổ biến nhất: Chạy script từ PowerShell 5.1 dùng lệnh `Invoke-RestMethod` mà không chỉ định charset UTF-8 (PowerShell 5.1 mặc định encode bằng ISO-8859-1 và vứt bỏ các byte dấu tiếng Việt).
  * **Cách khắc phục chuẩn trong PowerShell:**
    ```powershell
    $body = [System.Text.Encoding]::UTF8.GetBytes($jsonPayload)
    Invoke-RestMethod -Uri "http://localhost:8000/api/agents/external/start" -Method Post -Body $body -ContentType "application/json; charset=utf-8"
    ```
  * **Cách khắc phục chuẩn trong Python Client:**
    ```python
    import os, sys
    os.environ["PYTHONUTF8"] = "1"
    # Hoặc sử dụng client SDK có sẵn:
    from agent_sdk import AgentTracker
    tracker = AgentTracker("http://localhost:8000")
    ```

---

### 🛰️ Lưu Ý 11: Kiểm Thử Thực Tế Bằng 3 Hệ Thống Vệ Tinh (Mock Systems) & Hướng Dẫn Đọc Chỉ Số

Trước khi triển khai lên production, bạn có thể kiểm thử toàn diện khả năng giám sát và chốt chặn an toàn của AgentGuard bằng bộ 3 vệ tinh mô phỏng môi trường doanh nghiệp thực tế nằm trong thư mục \mock-systems/\:

1. **E-commerce Customer Care Agent (\:8010\ - FastAPI)**: Mô phỏng bot tư vấn bán hàng, tách bạch chi phí suy luận LLM (tính tiền token API) vs công cụ nội bộ tra cứu kho/mã giảm giá (0₫ - Deterministic).
2. **FinTech Transaction Agent (\:8020\ - Node.js/Express)**: Mô phỏng bot chuyển khoản ngân hàng, tự động kích hoạt chốt chặn **Human-in-the-Loop** đưa phiên về trạng thái \WAITING_APPROVAL\ để người vận hành duyệt/từ chối trên Dashboard.
3. **Autonomous Web Crawler (\:8030\ - Python Worker)**: Mô phỏng worker cào dữ liệu tự hành, kích hoạt thuật toán **Loop Detector** (băm SHA-256 đối số) ngắt phiên khẩn cấp sau 2 lần lặp liên tiếp.

**Lệnh kiểm thử tự động 1 chạm:**
\\ash
uv run python mock-systems/run_all.py --test
\
> 📖 **Xem hướng dẫn chi tiết toàn diện từ cài đặt, kiểm thử tới cách đọc từng chỉ số Dashboard & Langfuse tại:**  
> 👉 [\docs/MOCK_SYSTEMS_GUIDE.md\](MOCK_SYSTEMS_GUIDE.md) và giao diện trực tiếp tại [http://localhost:8000/guide](http://localhost:8000/guide).

---

## 💖 8. Cộng Đồng, Phản Hồi & Tài Trợ (Support & Donate)

Chúng tôi rất hoan nghênh những phản hồi, ý tưởng và đóng góp từ cộng đồng:
- **⭐ Tặng 1 Sao Trên GitHub**: [GitHub Repository](https://github.com/longnguyen97-full/agent-management-system/)
- **💬 Báo Cáo Lỗi & Đề Xuất Chốt Chặn**: [GitHub Issues](https://github.com/longnguyen97-full/agent-management-system/issues)

### ☕ Mời Tác Giả Ly Cà Phê (Ủng Hộ & Tài Trợ)
Nếu bạn thấy **AgentGuard** hữu ích và muốn tiếp sức cho việc duy trì & phát triển mã nguồn mở miễn phí, hãy ủng hộ tác giả qua mã QR dưới đây:

<div align="center">
  <img src="https://i.postimg.cc/Zqg3GGpG/qrcode.jpg" alt="AgentGuard Donation QR Code" width="220" style="border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
  <br/>
  <em>Quét mã VietQR qua ứng dụng Ngân hàng / Mobile Banking</em>
  <br/>
  <strong>Chân thành cảm ơn sự đồng hành và ủng hộ của bạn! ❤️</strong>
</div>
