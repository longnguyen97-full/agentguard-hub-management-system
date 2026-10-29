# 🌐 Mock Host Systems - Các Hệ Thống Agent Vệ Tinh Mẫu

Thư mục này chứa **3 hệ thống máy chủ dịch vụ độc lập** chạy Agent thực thụ (khác biệt hoàn toàn so với script giả lập). Mỗi hệ thống đại diện cho một bài toán doanh nghiệp ngoài đời thực, nhúng trực tiếp **AgentGuard Sentinel SDK** để kết nối về Hub trung tâm (:8000).

---

## 🏛️ Danh Sách 3 Hệ Thống

| Hệ Thống | Ngôn Ngữ / Cổng | Vai Trò Nghiệp Vụ | Chốt Chặn Kiểm Thử Trên Hub (:8000) |
| :--- | :--- | :--- | :--- |
| **1. E-Commerce Service** | Python / FastAPI<br>`http://localhost:8010` | Web Backend bán hàng có Agent CSKH tự động tra cứu đơn hàng & tặng voucher. | 🟢 **Luồng chuẩn 100% (Compliant)**: Đo lường chính xác đoạn tốn token vs đoạn code tất định 0đ. |
| **2. Fintech Service** | Node.js Native<br>`http://localhost:8020` | Service ví điện tử có Agent tài chính tự động phân tích & chuẩn bị chuyển tiền. | ⏸️ **Human-in-the-Loop Approval**: Lệnh chuyển tiền bị tạm dừng ngay lập tức; chờ con người bấm duyệt trên Dashboard. |
| **3. Crawler Worker** | Python Worker<br>`http://localhost:8030` | Tiến trình tự động hóa cào dữ liệu chuyên sâu. | 🛡️ **Loop Detector**: Cắt luồng khi kẹt phân trang.<br>💰 **Budget Limiter**: Khóa tác vụ khi vượt trần $0.10. |

---

## 🚀 Hướng Dẫn Sử Dụng

### 1. Khởi động nhanh cả 3 hệ thống và kích hoạt test tự động:
Từ thư mục gốc `agent-management-system`:
```bash
uv run python mock-systems/run_all.py --test
```

### 2. Khởi chạy từng hệ thống riêng biệt:
- **Hệ thống 1 (E-Commerce :8010)**:
  ```bash
  cd mock-systems/ecommerce-service
  uv run python app.py
  ```
- **Hệ thống 2 (Fintech Node.js :8020)**:
  ```bash
  cd mock-systems/fintech-service
  node server.js
  ```
- **Hệ thống 3 (Crawler Worker :8030)**:
  ```bash
  cd mock-systems/crawler-worker
  uv run python worker.py
  ```

---

## 🧪 Gửi Request Thử Nghiệm Thủ Công (cURL / Postman / PowerShell)

#### Test 1: Gửi tin nhắn khách hàng vào E-Commerce (:8010)
```bash
curl -X POST http://localhost:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Kiểm tra đơn hàng DH-1002", "order_id": "DH-1002"}'
```

#### Test 2: Yêu cầu chuyển tiền vào Fintech Service (:8020)
```bash
curl -X POST http://localhost:8020/api/transfer \
  -H "Content-Type: application/json" \
  -d '{"account_id": "ACC-9988", "recipient": "EVN-ELECTRIC", "amount": 2500000}'
```
> 👉 *Lúc này hãy mở `http://localhost:8000/dashboard` để thấy yêu cầu chờ phê duyệt màu cam xuất hiện realtime!*

#### Test 3: Kích hoạt tác vụ cào kẹt vòng lặp vào Crawler Worker (:8030)
```bash
curl -X POST http://localhost:8030/api/crawl/loop
```
> 👉 *Lập tức AgentGuard Hub sẽ kích hoạt chốt chặn vòng lặp và ngắt tác vụ.*

