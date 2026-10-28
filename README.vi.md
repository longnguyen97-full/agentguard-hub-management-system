# Agent Observability & Management System (Hệ Thống Giám Sát & Quản Trị AI Agent)

<p align="center">
  <a href="README.md">🇬🇧 English</a> •
  <a href="README.vi.md">🇻🇳 Tiếng Việt</a>
</p>

Một hệ sinh thái giám sát và quản trị AI Agent chuyên nghiệp theo mô hình **Hybrid (Lai)**:
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

## 🌟 Điểm Nhấn Nổi Bật

1. **Active Control (Can thiệp thời gian thực)**: Trong khi các công cụ như Langfuse hay Phoenix thuần túy là quan sát thụ động (ghi nhận log sau khi sự việc đã diễn ra), hệ thống này trao quyền can thiệp ngay lập tức: ngắt tiến trình tức thì, chặn vòng lặp, kiểm soát ngân sách.
2. **Human-in-the-Loop (Phê duyệt trước khi hành động)**: Tự động tạm dừng Agent khi chuẩn bị gọi các công cụ nhạy cảm (như sửa đổi cơ sở dữ liệu, gửi email, giao dịch tiền) và yêu cầu người quản trị bấm Authorize trên Dashboard.
3. **Phân định rõ ràng Chi phí (Billable vs Non-Billable)**: Tách bạch giữa bước suy luận LLM tốn phí token và các bước xử lý code tất định nội bộ (miễn phí 0đ).
4. **Hỗ trợ Song ngữ Tiền tệ (USD & VND)**: Tự động quy đổi tỷ giá trực tiếp trên giao diện Dashboard.
5. **Client SDK siêu nhẹ (`agent_sdk.py`)**: Tích hợp bất kỳ Agent nào (dù viết bằng LangChain, CrewAI, AutoGen hay script Python thuần) vào hệ thống chỉ với vài dòng code.

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh

### 1. Chuẩn bị môi trường
- Python >= 3.11
- Trình quản lý gói siêu tốc [`uv`](https://docs.astral.sh/uv/) (khuyên dùng)
- Docker & Docker Compose

### 2. Khởi chạy Cụm Hạ Tầng Langfuse Observability
Cụm Langfuse lưu trữ toàn bộ lịch sử trace, log token và chi phí. Trong thư mục gốc của dự án:
```bash
docker compose up -d
```
> Giao diện Langfuse Web sẽ khả dụng tại: **[http://localhost:3000](http://localhost:3000)**  
> *Tài khoản mặc định:* `admin@example.com` / `AdminPassword123!`

---

### 3. Khởi chạy Custom Agent Management Backend & Dashboard

1. Đồng bộ thư viện bằng `uv`:
```bash
uv sync --all-groups
```

2. Khởi chạy hệ thống:
```bash
uv run run.py
# hoặc dùng lệnh rút gọn:
uv run agent-hub
```

Ứng dụng sẽ khởi động trên:
- 📊 **Agent Control Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- 📖 **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- 🔍 **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Các Kịch Bản Kiểm Thử Có Sẵn (Demo Scenarios)

Truy cập Dashboard tại `http://localhost:8000/dashboard`, bạn có thể bấm thử ngay các kịch bản mẫu:

### Kịch bản 1: Luồng chuẩn (Standard 3-Step Agent)
- Agent suy nghĩ (Reasoning) -> Gọi tool `search_knowledge_base` -> Gọi tool `calculate_metric` -> Trả về kết quả tổng hợp.
- **Quan sát:** Token và ước tính chi phí USD/VND được tính toán realtime theo từng bước và ghi nhận lên Langfuse.

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

### Kịch bản 5: Kết nối Agent ngoài qua SDK
- Chạy demo Agent bán hàng độc lập nhúng SDK:
```bash
uv run python examples/external_agent_demo.py
```
- Quan sát Agent tự động gửi log theo thời gian thực về Dashboard và hiển thị phân định chi phí miễn phí vs tốn phí!

---

## 🧪 Chạy Kiểm Thử Tự Động (Automated Test Suite)

Dự án đi kèm bộ test toàn diện kiểm tra tất cả các cơ chế bảo vệ:
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

```
agent-management-system/
├── docker-compose.yml       # Cụm hạ tầng Langfuse (Web, Worker, Postgres, Redis, ClickHouse, MinIO)
├── .env.example             # Mẫu biến môi trường
├── pyproject.toml           # Cấu hình dự án và dependencies
├── run.py                   # Script khởi chạy nhanh backend
├── Dockerfile               # Đóng gói backend container
├── agent_sdk.py             # Client SDK nhẹ để tích hợp Agent bên ngoài
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
