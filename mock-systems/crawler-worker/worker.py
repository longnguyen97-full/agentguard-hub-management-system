"""
HỆ THỐNG 3: AUTONOMOUS DATA CRAWLER WORKER (Port 8030 - Python)
Service tự động hóa cào dữ liệu chuyên sâu.
Demo 2 rủi ro kỹ thuật lớn nhất của AI Agent:
1. Vòng lặp vô tận (Infinite Loop Trap) do web lỗi phân trang.
2. Tràn ngân sách tài chính (Budget Overrun) do cào dữ liệu ồ ạt.
"""

import sys
import time
import uvicorn
from fastapi import FastAPI
from agent_sdk import AgentTracker

app = FastAPI(title="Autonomous Data Crawler Service", version="1.0.0")
tracker = AgentTracker(endpoint="http://localhost:8000")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "Autonomous Data Crawler Worker",
        "port": 8030,
        "capabilities": ["loop_demo", "budget_overrun_demo", "kill_switch_demo"]
    }


@app.post("/api/crawl/loop")
def trigger_infinite_loop_job():
    """
    Kịch bản 1: Bot bị kẹt vòng lặp do nút phân trang trang web đối tác bị lỗi JS.
    Agent cố chấp gọi lại 3 lần liên tiếp y hệt -> Kích hoạt Loop Detector của AgentGuard!
    """
    print("[Crawler Worker :8030] ⚠️ Bắt đầu tác vụ cào dữ liệu gặp lỗi phân trang (Loop Trap)...")
    session = tracker.start_run(
        agent_name="Autonomous_Crawler_Worker",
        prompt="Cào toàn bộ 500 bài viết từ diễn đàn công nghệ qua nút Next Page",
        max_steps=8,
        budget_usd=0.25
    )

    # Bước 1: Tải trang 1 thành công
    session.log_step(
        thought="Đang tải trang 1 chuyên mục công nghệ.",
        tool_name="fetch_forum_page",
        tool_input={"page": 1, "category": "ai"},
        tool_output={"articles": 10, "has_next": True},
        tokens_used=120,
        cost_usd=0.00003,
        latency_ms=180.0
    )

    # Bước 2: Nút Next page lỗi, bot thử tải trang 2
    session.log_step(
        thought="Nút chuyển trang bị treo JavaScript, bot gửi lại request tải trang 2.",
        tool_name="fetch_forum_page",
        tool_input={"page": 2, "category": "ai"},
        tool_output={"error": "Pagination timeout", "retried": True},
        tokens_used=120,
        cost_usd=0.00003,
        latency_ms=190.0
    )

    # Bước 3: Bot lặp lại y hệt tham số lần 2
    session.log_step(
        thought="Chưa lấy được kết quả trang 2, bot tiếp tục gọi lại y hệt tham số lần thứ 2.",
        tool_name="fetch_forum_page",
        tool_input={"page": 2, "category": "ai"},
        tool_output={"error": "Pagination timeout", "retried": True},
        tokens_used=120,
        cost_usd=0.00003,
        latency_ms=190.0
    )

    # Bước 4: Lặp lại lần thứ 3 -> CHẶN ĐỨNG BỞI LOOP DETECTOR!
    session.log_step(
        thought="Bot cố chấp gọi lại trang 2 lần thứ 3 mà không có logic ngắt -> KÍCH HOẠT CHỐT CHẶN VÒNG LẶP!",
        tool_name="fetch_forum_page",
        tool_input={"page": 2, "category": "ai"},
        tool_output=None,
        tokens_used=120,
        cost_usd=0.00003,
        latency_ms=190.0
    )

    session.fail("TERMINATED: AgentGuard Loop Detector đã phát hiện hành vi lặp vô tận và ngắt tiến trình thành công!")
    return {
        "success": False,
        "reason": "INFINITE_LOOP_DETECTED",
        "message": "Tiến trình cào dữ liệu đã bị AgentGuard ngắt khẩn cấp do phát hiện gọi tool trùng lặp 3 lần liên tiếp.",
        "hub_run_id": session.run_id
    }


@app.post("/api/crawl/budget")
def trigger_budget_overrun_job():
    """
    Kịch bản 2: Bot cào ồ ạt tài liệu nặng khiến chi phí vượt ngưỡng trần $0.10.
    AgentGuard Budget Guardrail lập tức khóa tác vụ!
    """
    print("[Crawler Worker :8030] ⚠️ Bắt đầu tác vụ cào dữ liệu nặng gây tràn ngân sách...")
    session = tracker.start_run(
        agent_name="Greedy_Scraper_Agent",
        prompt="Tải toàn bộ 300 tệp báo cáo tài chính nặng của các tập đoàn",
        max_steps=5,
        budget_usd=0.10  # Ngân sách chỉ cho phép $0.10
    )

    # Đợt 1: Tốn $0.05
    session.log_step(
        thought="Tải đợt 1: 50 tài liệu nặng.",
        tool_name="download_heavy_pdf_bundle",
        tool_input={"bundle_id": "batch_1"},
        tokens_used=12000,
        cost_usd=0.055,
        latency_ms=650.0
    )

    # Đợt 2: Tốn thêm $0.06 -> Tổng chi phí thành $0.115 (VƯỢT NGÂN SÁCH $0.10)
    session.log_step(
        thought="Tải đợt 2: 80 tài liệu tiếp theo khiến chi phí vượt quá giới hạn ngân sách $0.10!",
        tool_name="download_heavy_pdf_bundle",
        tool_input={"bundle_id": "batch_2"},
        tokens_used=15000,
        cost_usd=0.065,
        latency_ms=720.0
    )

    session.fail("TERMINATED: Chi phí $0.120 đã vượt trần ngân sách cho phép ($0.10). AgentGuard Budget Guardrail đã ngắt tiến trình.")
    return {
        "success": False,
        "reason": "BUDGET_OVERRUN",
        "message": "Tác vụ đã bị AgentGuard khóa khẩn cấp do vượt trần ngân sách tài chính.",
        "hub_run_id": session.run_id
    }


if __name__ == "__main__":
    print("🚀 Khởi chạy Hệ Thống 3 (Autonomous Crawler Worker) trên cổng 8030...")
    uvicorn.run(app, host="0.0.0.0", port=8030, log_level="info")

