# HƯỚNG DẪN TÍCH HỢP HỆ THỐNG GIÁM SÁT & QUẢN TRỊ AI AGENT
> **Dành cho**: Developer / Kỹ sư AI phát triển các hệ thống Agent độc lập (Client) muốn kết nối vào Agent Monitoring Hub.

---

## 1. Giới Thiệu Chung
Hệ thống **Agent Monitoring & Management Hub** cung cấp:
1. **Tracing nâng cao**: Theo dõi từng bước suy nghĩ (ReAct / Chain-of-Thought) và các lần gọi công cụ (Tool calls).
2. **Phân định chi phí chi tiết**: Tách bạch rõ ràng giữa **Đoạn tốn phí** (LLM Token Inference) và **Đoạn miễn phí** (Xử lý code tất định, Database, Local Tool, Cache).
3. **Đa tiền tệ**: Giám sát song song **USD ($)** và **Việt Nam Đồng (VND ₫)**.
4. **Guardrails an toàn**:
   * **Loop Detector**: Tự động ngắt khi Agent lặp vô tận.
   * **Budget Limiter**: Ngắt khi vượt giới hạn token hoặc ngân sách tiền.
   * **Human-in-the-Loop (HITL)**: Tạm dừng xin con người phê duyệt trước khi gọi lệnh nhạy cảm (sửa DB, gửi mail, thanh toán).
   * **Emergency Kill Switch**: Nút dừng khẩn cấp từ xa.

---

## 2. Lựa Chọn Phương Án Tích Hợp

| Phương Án | Mô tả | Phù hợp khi nào? |
| :--- | :--- | :--- |
| **Cách 1: Dùng Client SDK (`agent_sdk.py`)** | Nhúng class `AgentTracker` vào code của bạn; tự động bắn log và metrics về Hub qua HTTP. | Cực kỳ tiện lợi, chỉ cần 3 dòng code để thấy Agent hiện ngay trên Dashboard. |
| **Cách 2: Gọi qua REST API Trực Tiếp** | Gửi task qua HTTP POST `/api/agents/run` và nghe kết quả qua SSE stream. | Dành cho các hệ thống Web, App, Microservices không dùng Python (Node.js, Go, Java). |
| **Cách 3: Nhúng SDK Langfuse (`@observe`)** | Dùng decorator `@observe()` của Langfuse gửi trace chuyên sâu về Langfuse UI (:3000). | Phù hợp khi bạn cần đào sâu vào cây OpenInference và debug token chi tiết. |

---

## 3. Cách 1: Tích Hợp Bằng Client SDK (`agent_sdk.py`) - NHANH NHẤT

Dự án đã tích hợp sẵn thư viện client [`agent_sdk.py`](file:///d:/data-year-after-2023/about-2026/LAB/agent-management-system/agent_sdk.py). Bạn chỉ cần copy file này sang dự án Agent của bạn:

```python
from agent_sdk import AgentTracker

# 1. Khởi tạo tracker
tracker = AgentTracker(endpoint="http://localhost:8000")

# 2. Bắt đầu một phiên làm việc của Agent
session = tracker.start_run(
    agent_name="MyExternalAgent",
    prompt="Tra cứu thông tin khách hàng và tính toán công nợ",
    budget_usd=0.20
)

# 3. Ghi nhận bước suy luận hoặc gọi tool (tốn phí)
session.log_step(
    thought="Khách hàng yêu cầu kiểm tra số dư. Cần gọi tool query_balance.",
    tool_name="query_balance",
    tool_input={"customer_id": "cust_101"},
    tool_output={"balance_vnd": 5000000},
    tokens_used=180,
    cost_usd=0.00005,  # ~1.2 VND
    is_billable=True
)

# 4. Ghi nhận bước gọi tool tất định nội bộ (miễn phí 0đ)
session.log_step(
    thought="Chuyển đổi số dư sang định dạng tiền tệ đọc được.",
    tool_name="format_currency",
    tool_input={"amount": 5000000},
    tool_output="5.000.000 ₫",
    tokens_used=0,
    cost_usd=0.0,
    is_billable=False  # Miễn phí
)

# 5. Hoàn tất tác vụ
session.finish(final_output="Số dư hiện tại của bạn là 5.000.000 ₫.")
```
> 💡 *Bạn có thể chạy thử ngay kịch bản mẫu này bằng lệnh: `uv run python examples/external_agent_demo.py`.*

---

## 4. Cách 2: Tích Hợp Qua REST API Trực Tiếp

Hệ thống cung cấp REST API chuẩn OpenAPI tại `http://localhost:8000/docs`.

### Bước 1: Gửi yêu cầu khởi chạy Agent
Client gửi HTTP POST để khởi chạy tác vụ:

* **Endpoint**: `POST http://localhost:8000/api/agents/run`
* **Headers**: `Content-Type: application/json`
* **Body Request**:
```json
{
  "prompt": "Kiểm tra cơ sở dữ liệu và nâng cấp quota cho tài khoản #1024",
  "agent_name": "BillingOpsAgent",
  "model": "gpt-4o-mini",
  "max_steps": 10,
  "budget_usd": 0.50,
  "token_limit": 10000,
  "require_approval_tools": [
    "execute_database_update",
    "send_external_email",
    "delete_resource"
  ],
  "user_id": "customer_99"
}
```

* **Phản hồi mẫu (Response 200 OK)**:
```json
{
  "run_id": "run_a1b2c3d4e5",
  "agent_name": "BillingOpsAgent",
  "prompt": "Kiểm tra cơ sở dữ liệu...",
  "status": "RUNNING",
  "current_step": 0,
  "max_steps": 10,
  "total_tokens": 0,
  "total_cost_usd": 0.0,
  "total_cost_vnd": 0.0,
  "langfuse_trace_url": "http://localhost:3000/trace/run_a1b2c3d4e5"
}
```

---

### Bước 2: Theo dõi tiến trình Realtime qua Server-Sent Events (SSE)
Client có thể lắng nghe tiến trình từng giây qua SSE mà không cần polling liên tục:

* **Endpoint**: `GET http://localhost:8000/api/agents/stream`

#### Ví dụ bằng Python Client (`httpx`):
```python
import httpx
import json

async def listen_agent_events():
    url = "http://localhost:8000/api/agents/stream"
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.aiter_lines(url) as response:
            async for line in response:
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    event_type = event.get("type")
                    
                    if event_type == "step_completed":
                        step = event["step"]
                        print(f"[Bước {step['step_number']}] Tool: {step['tool_name']} | Chi phí: {step['cost_usd']}$ (~{step['cost_vnd']}₫)")
                    elif event_type == "status_changed":
                        print(f"Trạng thái mới: {event['status']}")
                    elif event_type == "run_finished":
                        print(f"Hoàn thành! Kết quả: {event.get('final_output')}")
```

#### Ví dụ bằng JavaScript / Node.js (Browser / Frontend):
```javascript
const eventSource = new EventSource("http://localhost:8000/api/agents/stream");

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "step_completed") {
    console.log(`Đã chạy xong bước ${data.step.step_number}:`, data.step);
  }
};
```

---

### Bước 3: Phê duyệt tác vụ nhạy cảm (Human-in-the-Loop)
Khi Agent chạm vào tool nhạy cảm (thuộc danh sách `require_approval_tools`), trạng thái của Agent sẽ chuyển thành **`WAITING_APPROVAL`**.

Để duyệt cho phép chạy tiếp hoặc từ chối:
* **Endpoint**: `POST http://localhost:8000/api/agents/runs/{run_id}/approve`
* **Body**:
```json
{
  "approved": true,
  "user": "lead_engineer@company.com",
  "comment": "Đã kiểm tra tài khoản, cho phép nâng quota"
}
```
*(Nếu muốn từ chối: truyền `"approved": false`)*

---

### Bước 4: Kích hoạt Nút dừng khẩn cấp (Emergency Kill Switch)
Nếu phát hiện Agent chạy sai hướng hoặc nghi ngờ bị tấn công Prompt Injection:

* **Endpoint**: `POST http://localhost:8000/api/agents/runs/{run_id}/kill`
* Ngay lập tức, luồng chạy của Agent sẽ bị ngắt và trạng thái chuyển sang **`KILLED`**.

---

## 4. Cách 2: Tích Hợp Nhúng SDK Vào Codebase Agent Có Sẵn

Nếu bạn đã có sẵn mã nguồn Agent viết bằng Python và chỉ muốn gửi dữ liệu giám sát:

### Bước 1: Cài đặt thư viện
```bash
uv add langfuse
# hoặc: pip install langfuse
```

### Bước 2: Thiết lập cấu hình kết nối trong file `.env` của Agent
```env
LANGFUSE_PUBLIC_KEY=pk-lf-test
LANGFUSE_SECRET_KEY=sk-lf-test
LANGFUSE_HOST=http://localhost:3000
```

### Bước 3: Sử dụng Decorator `@observe()` để bọc các hàm
Tách bạch rõ **Đoạn tốn tiền** và **Đoạn miễn phí**:

```python
from langfuse.decorators import observe, langfuse_context
import openai

# 1. ĐOẠN TỐN PHÍ (LLM Reasoning): Tính token & tiền
@observe()
def agent_reasoning(user_input: str):
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_input}]
    )
    # Tự động ghi nhận prompt_tokens, completion_tokens và $ chi phí lên hệ thống
    return response.choices[0].message.content

# 2. ĐOẠN MIỄN PHÍ (Deterministic Tool): 0đ, không tốn token
@observe(as_type="tool")
def execute_database_query(sql_query: str):
    # Đoạn này chạy code Python thuần hoặc truy vấn SQL local -> HOÀN TOÀN MIỄN PHÍ
    # Hệ thống chỉ ghi nhận Latency (ms) và Input/Output
    langfuse_context.update_current_observation(
        metadata={"is_billable": False, "cost": 0}
    )
    return {"status": "ok", "rows": 10}

# 3. HÀM ĐIỀU PHỐI TỔNG
@observe(as_type="agent")
def run_my_custom_agent(prompt: str):
    thought = agent_reasoning(prompt)      # Tốn phí API
    result = execute_database_query(thought) # Miễn phí
    return result
```

---

## 5. Bảng Phân Định: Đoạn Tốn Phí vs Đoạn Miễn Phí

| Loại Thao Tác | Bản Chất | Tốn Phí Không? | Các Chỉ Số Cần Giám Sát |
| :--- | :--- | :--- | :--- |
| **LLM Call (GPT-4o, Claude, Gemini)** | Suy luận xác suất (Probabilistic Reasoning) | 💸 **CÓ TỐN PHÍ** | Prompt Tokens, Completion Tokens, USD/VND, TTFT Latency |
| **Local Tool / Code Python thuần** | Xử lý tất định (Deterministic Logic) | ⚡ **MIỄN PHÍ (0đ)** | Latency thực thi (ms), Trạng thái lỗi/thành công |
| **Truy vấn SQL / Vector DB nội bộ** | Truy xuất dữ liệu (Data Retrieval) | ⚡ **MIỄN PHÍ (0đ)** | Query Latency (ms), Số lượng record trả về |
| **Prompt Caching Hit (OpenAI/Anthropic)** | Tái sử dụng ngữ cảnh cũ | 🟢 **GIẢM 50% - 90%** | Cache hit rate, Cached tokens |
| **External Paid API (SerpAPI, Twilio)** | Gọi dịch vụ bên ngoài | 💸 **CÓ TỐN PHÍ** | Số lượt gọi (Requests count), Chi phí API bên thứ 3 |

---

## 6. Checklist Kiểm Tra Trước Khi Đưa Lên Production

- [ ] Đã cấu hình `USD_TO_VND_RATE` phù hợp với tỷ giá hiện hành.
- [ ] Đã khai báo danh sách `require_approval_tools` cho các thao tác nguy hiểm (Xóa dữ liệu, sửa bảng phân quyền, gửi thanh toán).
- [ ] Đã đặt mức `budget_usd` và `token_limit` tối đa cho mỗi phiên Agent để tránh rò rỉ ngân sách.
- [ ] Bật `LoopDetector` với ngưỡng lặp từ 2-3 lần để kịp thời chặn các vòng lặp ReAct vô tận.

