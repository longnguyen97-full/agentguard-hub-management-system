# CẨM NANG TOÀN DIỆN: THIẾT LẬP, KIỂM THỬ VÀ ĐỌC CHỈ SỐ VỚI MOCK-SYSTEMS
> **Dành cho**: Developer, QA Engineer và AI System Architect muốn kiểm thử khả năng kiểm soát, chốt chặn an toàn và giám sát chi phí của AgentGuard trên các hệ thống Agent thực tế.

---

## 1. Giới Thiệu & Kiến Trúc Cụm Vệ Tinh (Satellite Architecture)

Khác với các công cụ chỉ cung cấp vài dòng script mock giả lập trong bộ nhớ, **AgentGuard** đi kèm một **cụm 3 hệ thống máy chủ dịch vụ độc lập** (`mock-systems/`). Mỗi hệ thống đại diện cho một bài toán doanh nghiệp điển hình, chạy trên các stack công nghệ khác nhau (Python FastAPI, Node.js, Python Worker), nhúng trực tiếp **AgentGuard Sentinel SDK** để truyền dữ liệu và nhận lệnh can thiệp thời gian thực từ Hub trung tâm:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CỤM 3 HỆ THỐNG AGENT VỆ TINH (MOCK-SYSTEMS)                  │
├────────────────────────┬────────────────────────────────┬───────────────────────┤
│  1. E-Commerce Server  │       2. Fintech Service       │   3. Crawler Worker   │
│   (:8010 - FastAPI)    │       (:8020 - Node.js)        │     (:8030 - Python)  │
│ - CSKH & Tra cứu đơn   │ - Chuyển tiền & Hóa đơn        │ - Cào diễn đàn & web  │
│ - Luồng chuẩn 100%     │ - Chốt chặn Duyệt (HITL)       │ - Chặn vòng lặp & phí │
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

## 2. Thiết Lập Môi Trường (Setup Requirements)

### Điều kiện tiên quyết:
- **Python 3.10+** (khuyến nghị dùng trình quản lý gói siêu tốc `uv`).
- **Node.js 18+** (cần thiết để chạy Hệ thống 2: Fintech Service).
- **Docker Desktop** (khuyến nghị bật để chạy cụm Langfuse & ClickHouse).

### Quy trình 3 bước khởi động hạ tầng:

#### Bước 1: Khởi động cụm quan sát Langfuse & ClickHouse
Từ thư mục gốc dự án:
```bash
docker compose up -d
```
> Kiểm tra tại `http://localhost:3000` để đảm bảo Langfuse đã sẵn sàng.

#### Bước 2: Khởi động AgentGuard Control Plane (Hub :8000)
Mở một cửa sổ Terminal mới:
```bash
uv run run.py
```
Hoặc:
```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

#### Bước 3: Xác nhận Hub đã trực tuyến (Health Check)
Mở trình duyệt truy cập:
👉 `http://localhost:8000/health`
Kết quả trả về JSON:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "service": "AgentGuard Control Plane",
  "active_runs": 0
}
```

---

## 3. Ba Phương Thức Chạy Kiểm Thử Mock Systems

### Phương Thức A (Khuyến Nghị): Test Tự Động 1-Lệnh Duy Nhất (All-in-One Orchestrator)
Đây là cách nhanh nhất để trải nghiệm toàn diện hệ thống:
```bash
uv run python mock-systems/run_all.py --test
```
**Quy trình tự động thực thi:**
1. Bộ điều phối tự động bật ngầm cả 3 server (`:8010`, `:8020`, `:8030`).
2. Chờ 3.5 giây để các cổng mạng sẵn sàng lắng nghe.
3. Tự động bắn 3 gói tin nghiệp vụ thực tế vào từng hệ thống:
   - Gửi yêu cầu hỏi đơn hàng vào E-Commerce (`:8010`).
   - Gửi yêu cầu chuyển tiền hóa đơn EVN vào Fintech (`:8020`).
   - Kích hoạt tác vụ cào kẹt phân trang vào Crawler (`:8030`).
4. Toàn bộ trajectory, tokens, chi phí và trạng thái được bắn trực tiếp lên Dashboard `:8000`.
5. Tự động giải phóng các tiến trình và đóng cổng mạng an toàn sau khi kết thúc.

---

### Phương Thức B: Chạy Chế Độ Nền (Daemon Mode) Để Thử Nghiệm Tương Tác
Nếu bạn muốn giữ cả 3 server chạy nền để tự mình gửi request kiểm thử qua cURL, Postman hoặc Swagger:
```bash
uv run python mock-systems/run_all.py --daemon
```
> Khi muốn dừng cụm server, chỉ cần nhấn `Ctrl + C` trên cửa sổ Terminal.

---

### Phương Thức C: Khởi Chạy Độc Lập Từng Dịch Vụ
Bạn có thể mở riêng từng cửa sổ terminal để quan sát log chi tiết của từng Agent:

#### 1. Hệ thống E-Commerce Service (:8010)
```bash
cd mock-systems/ecommerce-service
uv run python app.py
```

#### 2. Hệ thống Fintech & E-Wallet (:8020 - Node.js)
```bash
cd mock-systems/fintech-service
node server.js
```

#### 3. Hệ thống Crawler Worker (:8030)
```bash
cd mock-systems/crawler-worker
uv run python worker.py
```

---

## 4. Chi Tiết Nghiệp Vụ & Kịch Bản Của 3 Hệ Thống Vệ Tinh

### 🛍️ Hệ Thống 1: E-Commerce Customer Care (:8010 - FastAPI)
- **Bài toán nghiệp vụ**: Bot tư vấn bán hàng tự động chăm sóc khách, tra cứu đơn hàng trong cơ sở dữ liệu nội bộ và tự quyết định cấp mã giảm giá đền bù nếu đơn hàng bị giao trễ.
- **Chốt chặn kiểm thử**: **Luồng Hợp Lệ Chuẩn Mực 100% (Compliant Flow)**.
- **Đặc điểm kỹ thuật**:
  - Phân tách rành mạch:
    - *Lượt gọi LLM suy luận ReAct*: Đánh dấu `is_billable: True`, tính phí token API theo tỷ giá thị trường.
    - *Lượt gọi tool tra cứu SQLite*: Đánh dấu `is_billable: False`, hệ thống gán nhãn **Tất định (Miễn phí 0₫)** và 0 tokens để không làm sai lệch báo cáo tài chính.
- **Lệnh cURL test thủ công**:
  ```bash
  curl -X POST http://localhost:8010/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Đơn hàng DH-1002 của tôi giao đến đâu rồi shop ơi?", "order_id": "DH-1002"}'
  ```

---

### 💳 Hệ Thống 2: Fintech & E-Wallet Service (:8020 - Node.js)
- **Bài toán nghiệp vụ**: Trợ lý tài chính AI tự động phân tích hóa đơn sinh hoạt và thực hiện thanh toán tiền điện/nước qua tài khoản ngân hàng.
- **Chốt chặn kiểm thử**: **Human-in-the-Loop Approval (HITL)**.
- **Đặc điểm kỹ thuật**:
  - Khi Agent phân tích xong và chuẩn bị gọi tool đột biến tài chính `execute_bank_transfer` với số tiền 2.500.000₫, SDK lập tức gửi tín hiệu yêu cầu phê duyệt về AgentGuard Hub.
  - Tiến trình Node.js tự động **đóng băng (pause)** ở trạng thái `WAITING_APPROVAL`.
  - Trên Dashboard xuất hiện khung cảnh báo màu cam với 2 nút: **Duyệt (Authorize)** và **Từ Chối (Reject)**.
  - Nếu người quản trị bấm duyệt, Agent mới được phép tiếp tục giải ngân.
- **Lệnh cURL test thủ công**:
  ```bash
  curl -X POST http://localhost:8020/api/transfer \
    -H "Content-Type: application/json" \
    -d '{"account_id": "ACC-9988", "recipient": "EVN-ELECTRIC", "amount": 2500000}'
  ```

---

### 🕷️ Hệ Thống 3: Autonomous Crawler Worker (:8030 - Python Worker)
- **Bài toán nghiệp vụ**: Tiến trình tự động hóa thu thập báo cáo tài chính và tin tức chứng khoán trên các diễn đàn trực tuyến.
- **Chốt chặn kiểm thử**: **Loop Detector (Chặn Vòng Lặp Vô Tận)** & **Budget Guardrail (Khóa Trần Ngân Sách)**.
- **Đặc điểm kỹ thuật**:
  - Trang web bị lỗi vòng lặp chuyển hướng (chuyển qua lại giữa `page=2` và `page=1`).
  - Agent tiếp tục lặp lại lượt gọi tool `fetch_page` với cùng tham số hash.
  - Ngay ở lần lặp thứ 2, bộ lọc **Deterministic Tool Hash Interceptor** của AgentGuard can thiệp khẩn cấp: ngắt tiến trình ngay lập tức với mã `TERMINATED_LOOP` để bảo vệ tài khoản API khỏi bị cạn kiệt số dư ngoài ý muốn.
- **Lệnh cURL test thủ công**:
  ```bash
  curl -X POST http://localhost:8030/api/crawl/loop
  ```

---

## 5. Cẩm Nang Đọc & Phân Tích Các Chỉ Số Trên Dashboard (:8000/dashboard)

Sau khi chạy lệnh kiểm thử, hãy mở trình duyệt vào:
👉 **`http://localhost:8000/dashboard`**

### ⚠️ Lưu ý cốt lõi: Gạt công tắc sang "Live Mode: ON"
- **Simulation Mode (Màu vàng)**: Môi trường chạy thử các kịch bản mẫu giả lập có sẵn trong bộ nhớ của Hub.
- **Live Mode (Màu xanh lá)**: Hiển thị dữ liệu thực tế bắn về từ các hệ thống Agent ngoài (`mock-systems/` hoặc bot riêng của bạn).
> *Khi kiểm thử với mock-systems, hãy đảm bảo nút góc trên hiển thị:* **`Live Mode: ON`**.

---

### 📊 1. Thanh 4 Thẻ Chỉ Số Tổng Quan (Header Metrics Overview)

| Thẻ Chỉ Số | Ý Nghĩa Kỹ Thuật | Cách Đọc & Phân Tích Thực Tế |
| :--- | :--- | :--- |
| **Tổng Số Phiên Chạy (Total Agent Runs)** | Số lượng phiên làm việc độc lập được đăng ký vào Hub qua SDK. | Mỗi lượt khách hàng hỏi ở E-Commerce, mỗi lượt yêu cầu chuyển tiền ở Fintech hoặc một tác vụ cào dữ liệu được tính là 1 Run độc lập. |
| **Đang Chờ Phê Duyệt (Waiting Approval)** | Số tác vụ nhạy cảm đang bị đóng băng chờ con người can thiệp. | Khi chạy test Fintech (:8020), chỉ số này sẽ nhảy lên **1** (màu vàng cam). Cần bấm vào phiên chạy để duyệt. |
| **Tổng Token Ghi Nhận (Total Tokens)** | Tổng số lượng token thực tế tiêu tốn qua các bước suy luận ReAct. | Chỉ tính tổng token từ các bước có cờ `is_billable: True`. Các bước gọi tool nội bộ được tính 0 token. |
| **Ước Tính Chi Phí (Estimated Cost)** | Số tiền API phải trả, tự động quy đổi song song giữa **USD ($)** và **VND (₫)**. | Được tính theo đơn giá thời gian thực của Model (ví dụ GPT-4o-mini: \$0.15/M input, \$0.60/M output). Bấm nút **`USD ⇄ VND`** để chuyển đổi hiển thị. |

---

### 🔍 2. Cách Đọc Dòng Thời Gian Suy Luận (Step Trajectory Inspector)

Bấm chọn một phiên chạy bất kỳ ở cột bên trái (ví dụ `run_...` của `FintechAccountAgent` hoặc `OpsAnalystAgent`), cột bên phải sẽ hiển thị toàn bộ cây suy luận chi tiết:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ↳ Bước 1                                            180ms  245 tokens │
├────────────────────────────────────────────────────────────────────────┤
│ 🧠 LLM Reasoning (Có tính phí Token API):                     $0.0001 │
│ "Đã nhận yêu cầu chuyển tiền 2.500.000đ cho EVN. Tiến hành kiểm tra   │
│  hạn mức số dư tài khoản người dùng ACC-9988."                        │
├────────────────────────────────────────────────────────────────────────┤
│ 🛠️ Tool Call: check_account_balance         ⚡ Tất định (Miễn phí 0₫) │
│ Parameters: {"account_id": "ACC-9988"}                                 │
│ Result:     {"balance_vnd": 15400000, "status": "active"}             │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Bộ não suy luận (`🧠 LLM Reasoning`)**:
   - Thể hiện tư duy logic lập kế hoạch của Agent trước khi ra quyết định.
   - Hiển thị lượng token tiêu tốn (ví dụ `245 tokens`) và chi phí tính phí thực tế (`$0.0001`).
2. **Hành động gọi công cụ (`🛠️ Tool Call`)**:
   - Tên công cụ được triệu hồi (ví dụ: `search_knowledge_base`, `check_account_balance`, `fetch_page`).
   - Huy hiệu xanh lá **`⚡ Tất định (Miễn phí 0₫)`**: Chỉ báo minh bạch rằng bước này được thực thi bởi code nội bộ máy chủ, hoàn toàn không tốn tiền API OpenAI/Anthropic.
3. **Tham số đầu vào (`Parameters`) & Kết quả trả về (`Result`)**:
   - Hiển thị định dạng JSON chuẩn của dữ liệu truyền vào và phản hồi từ dịch vụ nội bộ.
4. **Hộp thoại can thiệp phê duyệt (`Human-in-the-Loop Approval Banner`)**:
   - Khi Agent bước sang lệnh chuyển tiền `execute_bank_transfer`, hệ thống khóa dừng và hiển thị:
     - 🟢 Nút **`Phê Duyệt & Tiếp Tục (Authorize)`**: Cho phép Agent tiếp tục chạy bước giải ngân.
     - 🔴 Nút **`Từ Chối Lệnh (Reject)`**: Hủy bỏ lệnh ngay lập tức và trả thông báo an toàn về cho người dùng.
5. **Nút Dừng Khẩn Cấp (`Emergency Kill Switch`)**:
   - Ở góc phải màn hình luôn có nút đỏ **Kill Switch**. Nếu thấy Agent chạy vòng lặp bất thường hoặc có dấu hiệu suy luận lạc đề, bấm nút này để hủy bỏ tiến trình ngay tức khắc.

---

### 📈 3. Quan Sát Tracing Chuyên Sâu Trên Langfuse Core (:3000)

Bên cạnh giao diện điều hành thời gian thực tại port `:8000`, toàn bộ các spans, traces và metrics còn được đồng bộ ngầm vào ClickHouse:
- Truy cập: **`http://localhost:3000`**
- Tại đây bạn có thể:
  - Xem cây biểu đồ Span Waterfall (thời gian phản hồi của từng microsecond).
  - So sánh chi phí giữa các phiên bản Prompt.
  - Phân tích độ trễ p95 / p99 của toàn bộ hệ thống Agent doanh nghiệp.

---

## 6. Xử Lý Sự Cố Thường Gặp (Troubleshooting)

1. **Lỗi cổng mạng bị chiếm dụng (`Port 8010/8020/8030 already in use`)**:
   - Nếu bạn đã chạy server trước đó và bị kẹt cổng, hãy tắt các tiến trình cũ:
     - Trên Windows: `Stop-Process -Name node, python -Force` (hoặc khởi động lại máy).
     - Trên Linux/macOS: `fuser -k 8010/tcp 8020/tcp 8030/tcp`.

2. **Lỗi không thấy phiên chạy trên Dashboard sau khi chạy test**:
   - Kiểm tra xem bạn đã gạt công tắc trên thanh điều hướng sang **`Live Mode: ON`** chưa (mặc định nếu đang ở Simulation Mode, hệ thống sẽ ẩn các phiên live từ bên ngoài).

3. **Lỗi ký tự tiếng Việt hiển thị thành dấu hỏi (`?`) trên Console Windows**:
   - Do terminal Windows PowerShell mặc định dùng bảng mã `cp1252`.
   - Trong code của AgentGuard đã tích hợp `sys.stdout.reconfigure(encoding='utf-8')`. Khi chạy thủ công, bạn có thể gõ:
     ```powershell
     [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
     ```

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
