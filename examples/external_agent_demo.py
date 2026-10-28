"""
Script giả lập một hệ thống bên ngoài (External System) nhúng SDK
và gửi dữ liệu giám sát về Agent Monitoring Hub.
"""

import time
import sys
from pathlib import Path

# Add root directory to sys.path so agent_sdk can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_sdk import AgentTracker


def run_external_sales_agent():
    print("🚀 Bắt đầu chạy Agent từ hệ thống ngoài (External E-commerce System)...")

    # 1. Khởi tạo kết nối tới Hub giám sát
    tracker = AgentTracker(endpoint="http://localhost:8000")

    # 2. Đăng ký một phiên làm việc mới
    session = tracker.start_run(
        agent_name="ExternalCustomerCareAgent",
        prompt="Hỗ trợ khách hàng tra cứu trạng thái đơn hàng #DH-9921 và gửi mã giảm giá",
        max_steps=5,
        budget_usd=0.20
    )
    print(f"✅ Đã đăng ký phiên giám sát! Run ID: {session.run_id}")
    print(f"👉 Mở ngay Dashboard để xem realtime: http://localhost:8000/dashboard\n")

    # 3. Bước 1: LLM suy luận & phân tích yêu cầu (TỐN PHÍ TOKEN)
    print("⏳ [Bước 1] LLM đang suy luận: Phân tích mã đơn hàng...")
    time.sleep(1.5)
    session.log_step(
        thought="Khách hàng yêu cầu kiểm tra đơn hàng #DH-9921. Cần gọi tool tra cứu database đơn hàng.",
        tool_name="order_database_query",
        tool_input={"order_id": "DH-9921"},
        tool_output={"status": "DELIVERED", "delivered_at": "2026-10-27 14:30", "total_vnd": 450000},
        tokens_used=240,
        cost_usd=0.00008,  # ~2 VND
        latency_ms=320.0,
        is_billable=True
    )
    print("   -> Đã bắn log bước 1 lên Dashboard!")

    # 4. Bước 2: Gọi Tool tất định (MIỄN PHÍ 0đ)
    print("⏳ [Bước 2] Gọi tool tất định: Sinh mã coupon giảm giá 10%...")
    time.sleep(1.5)
    session.log_step(
        thought="Đơn hàng đã giao thành công. Tiến hành tạo mã voucher cảm ơn khách hàng qua hệ thống khuyến mãi nội bộ.",
        tool_name="generate_promo_coupon",
        tool_input={"customer_id": "cust_102", "discount_percent": 10},
        tool_output={"coupon_code": "THANKYOU10", "expiry": "2026-11-30"},
        tokens_used=0,
        cost_usd=0.0,      # MIỄN PHÍ
        latency_ms=45.0,
        is_billable=False
    )
    print("   -> Đã bắn log bước 2 (Tất định - 0đ) lên Dashboard!")

    # 5. Bước 3: Tổng hợp câu trả lời & Hoàn tất
    print("⏳ [Bước 3] Hoàn tất và gửi phản hồi cho khách hàng...")
    time.sleep(1.0)
    final_reply = (
        "Đơn hàng #DH-9921 của bạn đã được giao thành công vào hôm qua. "
        "Tặng bạn mã giảm giá THANKYOU10 (giảm 10% cho đơn hàng tiếp theo)!"
    )
    session.finish(final_output=final_reply)

    print("\n🎉 Hoàn thành xuất sắc!")
    print(f"Xem toàn bộ thông tin tại: http://localhost:8000/dashboard (chọn Run ID: {session.run_id})")


if __name__ == "__main__":
    try:
        run_external_sales_agent()
    except Exception as e:
        print(f"\n❌ Lỗi kết nối: {e}")
        print("💡 Hãy chắc chắn rằng bạn đã khởi động Hub giám sát trước bằng lệnh: uv run run.py")

