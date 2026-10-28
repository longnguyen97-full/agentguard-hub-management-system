# Hệ Thống Giám Sát & Quản Trị AI Agent (AI Agent Observability & Control Plane)

<p align="center">
  <a href="README.md">🇬🇧 English</a> •
  <a href="README.vi.md">🇻🇳 Tiếng Việt</a>
</p>

Một hệ sinh thái mã nguồn mở toàn diện phục vụ **Giám sát (Observability)** và **Điều khiển An toàn Vận hành (Control Plane & Guardrails)** cho các AI Agent tự hành:
- **Lõi Giám sát & Tracing chuyên sâu**: Tích hợp hạ tầng mã nguồn mở **Langfuse** (triển khai độc lập qua Docker Compose) để lưu trữ cây thực thi (Trace Trees), đo lường token, tính toán chi phí tự động theo model và đánh giá chất lượng (Evals).
- **Lõi Nghiệp vụ & Điều khiển Chủ động (Active Control Layer)**: Xây dựng bằng **Python / FastAPI** cung cấp cơ chế **Emergency Kill Switch**, **Phát hiện vòng lặp vô tận (Loop Detector)**, **Giới hạn ngân sách (Budget Guardrail)**, và quy trình **Phê duyệt của con người (Human-in-the-Loop Approval)** trước khi Agent thực thi các tool nhạy cảm.

---

## 📸 Giao Diện & Hình Ảnh Minh Họa

<div align="center">
  <img src="assets/dashboard-overview.png" alt="Tổng quan Dashboard Giám Sát Agent" width="95%" />
  <p><em>Giao diện Trung tâm Giám sát & Điều khiển Thời gian thực (Tiếng Anh mặc định kèm USD $)</em></p>
</div>

<br/>

<div align="center">
  <table width="100%">
    <tr>
      <td width="50%" align="center">
        <img src="assets/human-in-the-loop.png" alt="Phê duyệt của con người" />
        <br/>
        <strong>🛡️ Phê duyệt của Con người (Human-in-the-Loop)</strong>
        <br/>
        <em>Tự động dừng Agent khi chuẩn bị sửa Database; chờ người quản trị bấm Authorize trên UI.</em>
      </td>
      <td width="50%" align="center">
        <img src="assets/loop-guardrail.png" alt="Chốt chặn vòng lặp vô tận" />
        <br/>
        <strong>🛑 Chốt chặn Vòng lặp Vô tận (Loop Guardrail)</strong>
        <br/>
        <em>Phát hiện Agent lặp lại tool/tham số giống nhau và tự động ngắt tiến trình để bảo vệ ngân sách.</em>
      </td>
    </tr>
    <tr>
      <td colspan="2" align="center">
        <img src="assets/vietnamese-mode.png" alt="Chế độ Tiếng Việt và Tiền tệ VND" width="95%" />
        <br/>
        <strong>🌐 Chuyển Đổi Song Ngữ & Đồng Bộ Tiền Tệ Tự Động</strong>
        <br/>
        <em>1-click chuyển đổi giữa Tiếng Anh ($ USD) và Tiếng Việt (₫ VND) kèm tỷ giá quy đổi tức thì.</em>
      </td>
    </tr>
  </table>
</div>

---

## 🌟 Các Tính Năng & Năng Lực Cốt Lõi

1. **Điều Khiển Can Thiệp Thời Gian Thực (Active Control)**:
   - **Emergency Kill Switch**: Nút dừng khẩn cấp màu đỏ trên Dashboard hoặc API `POST /kill` giúp hủy tiến trình của Agent ngay tức thì.
   - **Loop Detector Guardrail**: Tự động nhận diện chữ ký tool call bị lặp lại và ngắt tiến trình trước khi Agent gây lãng phí tài khoản API.
   - **Budget Limiter**: Thiết lập trần cứng về số bước (steps), số lượng token và chi phí USD/VND cho mỗi phiên chạy.
2. **Quy Trình Phê Duyệt Của Con Người (Human-in-the-Loop)**:
   - Tự động chuyển trạng thái sang `WAITING_APPROVAL` khi Agent cố tình gọi các công cụ nhạy cảm (như cập nhật cơ sở dữ liệu, gửi email, giao dịch tiền). Người giám sát có toàn quyền kiểm tra tham số và bấm **Authorize** hoặc **Reject**.
3. **Phân Định Chi Phí Chi Tiết (Billable vs Non-Billable)**:
   - Tách bạch rõ ràng giữa các bước suy luận LLM tốn phí token và các bước xử lý code tất định nội bộ (miễn phí 0đ / 0₫).
4. **Hỗ Trợ Song Ngữ & Song Tệ (USD & VND)**:
   - Giao diện có nút chuyển đổi tức thì giữa Tiếng Anh (USD) và Tiếng Việt (VND), tự động cập nhật toàn bộ bảng điều khiển và nhãn hiển thị.
5. **Client SDK Siêu Nhẹ (`agent_sdk.py`)**:
   - Tích hợp bất kỳ Agent nào (dù viết bằng LangChain, CrewAI, AutoGen hay Python script thuần) vào trung tâm giám sát chỉ với vài dòng code.

---

## 🏛️ Sơ đồ Kiến trúc Hệ thống

```
                                 ┌──────────────────────────────────────────────┐
                                 │   Người Quản Trị / Operator Dashboard        │
                                 │   http://localhost:8000/dashboard            │
                                 └──────────────┬───────────────────────────────┘
                                                │
                                    (SSE & REST API Call)
                                                ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                 Custom Agent Management Service (FastAPI)                   │
  │                                                                             │
  │  ┌───────────────────────┐   ┌──────────────────────┐   ┌─────────────────┐ │
  │  │ Loop Guardrail        │   │ Budget Guardrail     │   │ Human-in-the-   │ │
  │  │ (Chặn lặp vô tận)     │   │ (Chặn vượt token/$)  │   │ Loop Approval   │ │
  │  └───────────────────────┘   └──────────────────────┘   └─────────────────┘ │
  │                                                                             │
  │  ┌───────────────────────┐   ┌──────────────────────┐   ┌─────────────────┐ │
  │  │ Emergency Kill Switch │   │ Agent Run Registry   │   │ OpenInference   │ │
  │  │ (Dừng Agent khẩn cấp) │   │ (Quản lý tiến trình) │   │ Telemetry Span  │ │
  │  └───────────────────────┘   └──────────────────────┘   └────────┬────────┘ │
  └──────────────────────────────────────────────────────────────────┼──────────┘
                                                                     │
                                                   (OTel / Langfuse Ingestion)
                                                                     ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                  Langfuse Tracing Stack (Docker Compose)                    │
  │                                                                             │
  │   - Langfuse Web UI (:3000)      - Langfuse Worker (:3030)                  │
  │   - PostgreSQL 17 (DB)           - ClickHouse (High-throughput analytics)   │
  │   - Redis (BullMQ queue)         - MinIO (Blob storage)                     │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh

### 1. Chuẩn bị môi trường
- Python >= 3.11
- Trình quản lý gói siêu tốc [`uv`](https://docs.astral.sh/uv/) (khuyên dùng)
- Docker & Docker Compose

### 2. Khởi chạy Cụm Hạ Tầng Langfuse Observability
Khởi động cụm dịch vụ tracing (Postgres, ClickHouse, Redis, MinIO, Langfuse UI & Worker):
```bash
docker compose up -d
```
> Giao diện Langfuse Web sẽ khả dụng tại: **[http://localhost:3000](http://localhost:3000)**  
> *Tài khoản mặc định:* `admin@example.com` / `AdminPassword123!`

### 3. Khởi chạy Custom Agent Management Backend & Dashboard
```bash
# Cài đặt và đồng bộ thư viện
uv sync --all-groups

# Khởi chạy hệ thống
uv run run.py
# hoặc dùng lệnh rút gọn:
uv run agent-hub
```

Ứng dụng sẽ hoạt động trên:
- 📊 **Agent Control Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- 📖 **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- 🔍 **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Các Kịch Bản Kiểm Thử Có Sẵn (Demo Scenarios)

Truy cập Dashboard tại `http://localhost:8000/dashboard`, bạn có thể bấm thử ngay 4 kịch bản mẫu:

| Kịch bản | Thao tác | Hiện tượng quan sát |
| :--- | :--- | :--- |
| **1. Luồng chuẩn 3 bước** | Agent suy luận + gọi công cụ tính toán. | Token và chi phí USD/VND tăng dần theo thời gian thực; timeline từng bước rõ ràng. |
| **2. Tác vụ nhạy cảm (HITL)** | Agent gọi `execute_database_update`. | Agent tự động tạm dừng ở trạng thái `WAITING_APPROVAL`. Người quản trị bấm **Authorize** hoặc **Reject**. |
| **3. Chặn vòng lặp (Loop Detector)** | Agent liên tục lặp lại tool cùng tham số. | Bộ lọc can thiệp sau 2 lần lặp, ngắt tiến trình an toàn để bảo vệ tài khoản API. |
| **4. Dừng khẩn cấp (Kill Switch)** | Bấm nút Kill Switch màu đỏ trên Dashboard. | Trạng thái chuyển ngay sang `KILLED` và tiến trình lập tức bị hủy bỏ. |

---

## 🔌 Tích Hợp Agent Bên Ngoài Bằng SDK Siêu Nhẹ

Bạn có thể kết nối bất kỳ Agent nào (dù viết bằng LangChain, CrewAI, AutoGen hay Python thuần) vào hệ thống bằng [`agent_sdk.py`](agent_sdk.py):

```python
from agent_sdk import AgentTracker

# 1. Khởi tạo tracker kết nối tới Hub
tracker = AgentTracker(endpoint="http://localhost:8000")

# 2. Đăng ký phiên chạy mới
session = tracker.start_run(
    agent_name="OrderSupportAgent",
    prompt="Hỗ trợ tra cứu đơn hàng #DH-9921 và tạo mã giảm giá",
    budget_usd=0.25
)

# 3. Ghi nhận bước suy luận / gọi tool LLM (tốn phí token)
session.log_step(
    thought="Khách hàng yêu cầu kiểm tra đơn hàng. Cần truy vấn database đơn hàng.",
    tool_name="order_database_query",
    tool_input={"order_id": "DH-9921"},
    tool_output={"status": "DELIVERED"},
    tokens_used=240,
    cost_usd=0.00008,
    is_billable=True
)

# 4. Ghi nhận bước xử lý nội bộ miễn phí (0₫ / $0.00)
session.log_step(
    thought="Đơn hàng hợp lệ. Sinh mã giảm giá cảm ơn khách hàng.",
    tool_name="generate_promo_coupon",
    tool_input={"discount_percent": 10},
    tool_output={"code": "THANKYOU10"},
    tokens_used=0,
    cost_usd=0.0,
    is_billable=False
)

# 5. Hoàn tất tác vụ
session.finish(final_output="Đã hoàn thành! Mã giảm giá THANKYOU10 đã được gửi.")
```

> Thử nghiệm ngay kịch bản mẫu này:
> ```bash
> uv run python examples/external_agent_demo.py
> ```

---

## 🧪 Chạy Kiểm Thử Tự Động (Automated Test Suite)

Dự án đi kèm bộ test toàn diện kiểm tra 100% các chốt chặn an toàn:
```bash
uv run pytest -v
```

Kết quả:
```text
tests/test_agent_system.py::test_standard_agent_execution PASSED         [ 16%]
tests/test_agent_system.py::test_loop_detector_guardrail PASSED          [ 33%]
tests/test_agent_system.py::test_budget_limit_guardrail PASSED           [ 50%]
tests/test_agent_system.py::test_human_in_the_loop_approval PASSED       [ 66%]
tests/test_agent_system.py::test_emergency_kill_switch PASSED            [ 83%]
tests/test_external_api.py::test_external_agent_ingestion_lifecycle PASSED [100%]
============================== 6 passed in 19s ===============================
```

---

## 📂 Cấu Trúc Thư Mục Dự Án

```text
agent-management-system/
├── assets/                  # Ảnh chụp màn hình & minh họa Dashboard
├── docker-compose.yml       # Cụm hạ tầng Langfuse (Web, Worker, Postgres, Redis, ClickHouse, MinIO)
├── .env.example             # Mẫu biến môi trường an toàn
├── pyproject.toml           # Cấu hình dự án và dependencies
├── run.py                   # Script khởi chạy nhanh backend (an toàn UTF-8 trên Windows)
├── Dockerfile               # Đóng gói backend container
├── agent_sdk.py             # Client SDK siêu nhẹ để nhúng vào Agent bên ngoài
├── backend/
│   └── app/
│       ├── main.py          # Khởi tạo FastAPI & mount router
│       ├── config.py        # Quản lý cấu hình Pydantic Settings
│       ├── core/
│       │   ├── tracer.py    # Wrapper tích hợp Langfuse v5 (OpenInference / OTel)
│       │   ├── guardrails.py# Bộ quy tắc: Loop detection, Budget limits, Approval check
│       │   └── registry.py  # Quản lý trạng thái Agent, Kill Switch & SSE broadcasting
│       ├── agents/
│       │   ├── base.py      # Abstract BaseAgent định nghĩa vòng đời quan sát
│       │   └── sample_agent.py # Agent mẫu thông minh hỗ trợ các kịch bản ReAct
│       ├── api/
│       │   └── routes.py    # REST API endpoints & Server-Sent Events (SSE)
│       ├── schemas/
│       │   └── agent.py     # Pydantic data schemas
│       └── templates/
│           └── dashboard.html # Giao diện giám sát & điều khiển thời gian thực (Đa ngôn ngữ & Song tệ)
├── examples/
│   └── external_agent_demo.py # Script demo tích hợp client SDK
├── docs/
│   └── CLIENT_INTEGRATION_GUIDE.md # Hướng dẫn chi tiết cách nhúng SDK
└── tests/
    ├── test_agent_system.py  # Bộ test bảo vệ và luồng nội bộ
    └── test_external_api.py  # Bộ test lifecycle tích hợp ngoài
```

---

## 📄 Giấy Phép (License)

Dự án phát hành dưới giấy phép [MIT License](LICENSE). Tự do sử dụng, chỉnh sửa và ứng dụng vào các hệ thống thương mại.
