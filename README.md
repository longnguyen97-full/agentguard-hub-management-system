# Agent Observability & Management System (Hệ Thống Giám Sát Agent)

Một hệ thống giám sát và quản trị AI Agent chuyên nghiệp theo mô hình **Hybrid**:
- **Lõi Observability & Tracing chuyên sâu**: Tích hợp nền tảng mã nguồn mở **Langfuse** (chạy độc lập qua Docker Compose) để theo dõi cây thực thi (Trace Trees), đo lường token, tính toán chi phí USD tự động cho từng model, và đánh giá chất lượng (Evals).
- **Lõi Nghiệp vụ & Điều khiển Tùy biến (Custom Control Layer)**: Xây dựng bằng **Python / FastAPI** cung cấp cơ chế **Emergency Kill Switch**, **Phát hiện vòng lặp vô tận (Loop Detector)**, **Giới hạn ngân sách (Budget Guardrail)**, và quy trình **Phê duyệt của con người (Human-in-the-Loop Approval)** trước khi Agent thực thi các tool nhạy cảm.

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
- Python >= 3.10
- Docker & Docker Compose

### 2. Khởi chạy Cụm Hạ Tầng Langfuse Observability
Cụm Langfuse lưu trữ toàn bộ lịch sử trace, log token và chi phí. Trong thư mục gốc của dự án:
```bash
docker compose up -d
```
> Giao diện Langfuse Web sẽ khả dụng tại: **[http://localhost:3000](http://localhost:3000)**
> *Tài khoản mặc định đã được cấu hình tự động:*
> - **Email:** `admin@example.com`
> - **Mật khẩu:** `AdminPassword123!`

---

### 3. Khởi chạy Custom Agent Management Backend & Dashboard

Dự án sử dụng trình quản lý gói siêu tốc **`uv`**. Khi dùng `uv run`, bạn **không bao giờ** bị lỗi `ModuleNotFoundError: No module named 'fastapi'` vì `uv` tự động đồng bộ môi trường và các thư viện cần thiết.

1. Đồng bộ thư viện bằng `uv`:
```bash
uv sync
```

2. Khởi chạy hệ thống:
```bash
uv run run.py
# hoặc dùng lệnh tắt:
uv run agent-hub
```

> **Ghi chú về lỗi `ModuleNotFoundError: No module named 'fastapi'`:**
> Lỗi này xuất hiện nếu bạn chạy `python run.py` hoặc `py run.py` bằng trình thông dịch Python mặc định của hệ điều hành mà quên kích hoạt virtual environment.
> Với `uv`, bạn chỉ cần chạy **`uv run run.py`** — `uv` sẽ luôn chọn đúng môi trường và nạp đầy đủ FastAPI.

Ứng dụng sẽ khởi động trên:
- 📊 **Agent Control Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- 📖 **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- 🔍 **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Các Kịch Bản Kiểm Thử Có Sẵn (Demo Scenarios)

Truy cập Dashboard tại `http://localhost:8000/dashboard`, bạn có thể bấm thử ngay 3 kịch bản mẫu:

### Kịch bản 1: Luồng chuẩn (Standard 3-Step Agent)
- Agent suy nghĩ (Reasoning) -> Gọi tool `search_knowledge_base` -> Gọi tool `calculate_metric` -> Trả về kết quả tổng hợp.
- **Quan sát:** Token và ước tính chi phí USD được tính toán realtime theo từng bước và ghi nhận lên Langfuse.

### Kịch bản 2: Tác vụ nhạy cảm (Human-in-the-Loop Approval)
- Agent thực hiện truy vấn DB, sau đó cố gắng gọi lệnh `execute_database_update` (được gắn cờ bảo vệ `require_approval_tools`).
- **Quan sát:**
  - Agent tự động **tạm dừng (PAUSE)**, trạng thái chuyển sang `WAITING_APPROVAL`.
  - Trên màn hình hiện yêu cầu phê duyệt kèm tham số truy vấn cụ thể.
  - Người quản trị bấm **"Authorize & Continue"** để cho phép Agent chạy tiếp, hoặc **"Reject"** để hủy bỏ lệnh.

### Kịch bản 3: Phát hiện vòng lặp vô tận (Loop Detector Guardrail)
- Giả lập tình huống Agent gặp lỗi tư duy và liên tục gọi một tool với tham số giống hệt nhau.
- **Quan sát:** Bộ lọc `LoopDetector` sẽ ngay lập tức ngắt tiến trình sau 2 lần lặp liên tiếp, ngăn chặn việc cạn kiệt tài khoản và spam API.

### Kịch bản 4: Nút dừng khẩn cấp (Emergency Kill Switch)
- Bất kỳ lúc nào Agent đang chạy, bạn có thể bấm nút **"Kill Switch"** màu đỏ trên Dashboard hoặc gọi `POST /api/agents/runs/{run_id}/kill` để hủy bỏ tiến trình ngay tức khắc.

---

## 🧪 Chạy Kiểm Thử Tự Động (Automated Test Suite)

Dự án đi kèm bộ test toàn diện kiểm tra tất cả các cơ chế bảo vệ (chạy trực tiếp bằng `uv`):
```bash
uv run pytest -v
```

Kết quả:
```text
tests/test_agent_system.py::test_standard_agent_execution PASSED         [ 20%]
tests/test_agent_system.py::test_loop_detector_guardrail PASSED          [ 40%]
tests/test_agent_system.py::test_budget_limit_guardrail PASSED           [ 60%]
tests/test_agent_system.py::test_human_in_the_loop_approval PASSED       [ 80%]
tests/test_agent_system.py::test_emergency_kill_switch PASSED            [100%]
============================== 5 passed in 18s ===============================
```

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
agent-management-system/
├── docker-compose.yml       # Cụm hạ tầng Langfuse (Web, Worker, Postgres, Redis, ClickHouse, MinIO)
├── .env                     # Biến môi trường hệ thống
├── .env.example             # Mẫu cấu hình
├── requirements.txt         # Danh sách thư viện Python
├── run.py                   # Script khởi chạy nhanh backend
├── Dockerfile               # Dockerfile đóng gói backend
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
│           └── dashboard.html # Giao diện giám sát & điều khiển thời gian thực
└── tests/
    └── test_agent_system.py # Bộ unit & integration tests
```

# agent-management-system
