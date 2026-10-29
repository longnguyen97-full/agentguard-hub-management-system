"""
HỆ THỐNG 1: E-COMMERCE CUSTOMER CARE SERVICE (Port 8010)
Dịch vụ Web bán hàng trực tuyến có Agent CSKH tự động tra cứu đơn hàng & chăm sóc khách.
Nhúng trực tiếp AgentGuard Sentinel SDK (agent_sdk.py).
"""

import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

# Nhập Sentinel SDK của AgentGuard
from agent_sdk import AgentTracker

app = FastAPI(title="E-Commerce Customer Support Service", version="1.0.0")

# Khởi tạo kết nối tới AgentGuard Hub (:8000)
HUB_URL = "http://localhost:8000"
tracker = AgentTracker(endpoint=HUB_URL)

# Mock Cơ sở dữ liệu đơn hàng
MOCK_ORDERS = {
    "DH-1001": {"status": "SHIPPING", "carrier": "GiaoHangNhanh", "eta": "Hôm nay 17:00", "total_vnd": 350000},
    "DH-1002": {"status": "DELIVERED", "carrier": "ViettelPost", "eta": "Đã giao hôm qua", "total_vnd": 680000},
    "DH-1003": {"status": "PROCESSING", "carrier": "Kho Tân Bình", "eta": "Đang đóng gói", "total_vnd": 1200000},
}


class ChatRequest(BaseModel):
    user_id: str = "customer_88"
    message: str = "Đơn hàng DH-1002 của tôi đã đến đâu rồi?"
    order_id: Optional[str] = "DH-1002"


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "E-Commerce Customer Care Service",
        "port": 8010,
        "agentguard_hub": HUB_URL
    }


@app.post("/api/chat")
def handle_customer_chat(req: ChatRequest):
    """
    Agent tiếp nhận tin nhắn khách hàng -> Báo cáo Hub -> Xử lý đơn hàng -> Trả lời khách.
    """
    order_id = req.order_id or "DH-1002"

    # 1. BẮT ĐẦU PHIÊN CHẠY: Sentinel SDK thông báo cho AgentGuard Hub
    session = tracker.start_run(
        agent_name="ECommerce_Support_Bot",
        prompt=f"Khách hàng {req.user_id} hỏi: '{req.message}'",
        max_steps=5,
        budget_usd=0.20,
        user_id=req.user_id
    )

    # 2. BƯỚC 1: LLM Reasoning phân tích câu hỏi (TỐN PHÍ TOKEN)
    session.log_step(
        thought=f"Khách hàng hỏi trạng thái đơn hàng {order_id}. Cần gọi công cụ tra cứu cơ sở dữ liệu đơn hàng.",
        tool_name="database_query_order",
        tool_input={"order_id": order_id},
        tokens_used=180,
        cost_usd=0.00005,
        latency_ms=210.0,
        is_billable=True
    )

    # 3. BƯỚC 2: Truy vấn dữ liệu nội bộ (MIỄN PHÍ 0đ / 0 TOKEN)
    order_data = MOCK_ORDERS.get(order_id, {"status": "NOT_FOUND"})
    session.log_step(
        thought=f"Đã tìm thấy đơn hàng {order_id}: trạng thái {order_data['status']}.",
        tool_name="format_order_details",
        tool_input={"order_id": order_id},
        tool_output=order_data,
        tokens_used=0,
        cost_usd=0.0,
        latency_ms=12.0,
        is_billable=False  # Đoạn miễn phí
    )

    # 4. BƯỚC 3: Sinh mã voucher cảm ơn khách hàng (MIỄN PHÍ 0đ)
    coupon_code = f"VIP-{order_id[-4:]}-OFF10"
    session.log_step(
        thought="Đơn hàng đã giao thành công. Tự động sinh mã voucher giảm 10% tặng khách hàng thân thiết.",
        tool_name="generate_customer_voucher",
        tool_input={"customer_id": req.user_id, "discount": 10},
        tool_output={"voucher": coupon_code, "valid_days": 30},
        tokens_used=0,
        cost_usd=0.0,
        latency_ms=15.0,
        is_billable=False
    )

    # 5. HOÀN TẤT VÀ PHẢN HỒI
    final_reply = (
        f"Dạ chào bạn! Đơn hàng #{order_id} của bạn có trạng thái: {order_data['status']} ({order_data['eta']}). "
        f"Shop gửi tặng bạn mã voucher tri ân: {coupon_code} (giảm 10% cho đơn tiếp theo) nhé!"
    )
    session.finish(final_output=final_reply)

    return {
        "success": True,
        "reply": final_reply,
        "order_details": order_data,
        "hub_run_id": session.run_id
    }


if __name__ == "__main__":
    print("🚀 Khởi chạy Hệ Thống 1 (E-Commerce Customer Service) trên cổng 8010...")
    uvicorn.run(app, host="0.0.0.0", port=8010, log_level="info")

