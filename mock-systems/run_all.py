"""
BỘ ĐIỀU PHỐI KHỞI CHẠY CẢ 3 HỆ THỐNG AGENT MẪU (MOCK HOST SYSTEMS)
- Hệ thống 1: E-Commerce Customer Care (:8010 - FastAPI)
- Hệ thống 2: Fintech & E-Wallet Service (:8020 - Node.js)
- Hệ thống 3: Data Crawler Worker (:8030 - Python)
"""

import sys
import time
import subprocess
import argparse
import httpx
from pathlib import Path

# Hỗ trợ UTF-8 cho Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
ECOMMERCE_DIR = ROOT_DIR / "ecommerce-service"
FINTECH_DIR = ROOT_DIR / "fintech-service"
CRAWLER_DIR = ROOT_DIR / "crawler-worker"

HUB_URL = "http://localhost:8000"
SYS1_URL = "http://localhost:8010"
SYS2_URL = "http://localhost:8020"
SYS3_URL = "http://localhost:8030"

processes = []


def is_port_online(url: str) -> bool:
    try:
        with httpx.Client(timeout=1.5) as client:
            return client.get(f"{url}/health").status_code == 200
    except Exception:
        return False


def start_services():
    print("==================================================================", flush=True)
    print("🚀 KHỞI CHẠY CỤM 3 HỆ THỐNG AGENT VỆ TINH ĐỘC LẬP (MOCK SYSTEMS)", flush=True)
    print("==================================================================", flush=True)

    # 1. Start Hệ Thống 1 (E-Commerce :8010)
    print("▶ Khởi động Hệ Thống 1: E-Commerce Customer Care (:8010)...", flush=True)
    p1 = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=str(ECOMMERCE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(p1)

    # 2. Start Hệ Thống 2 (Fintech Node.js :8020)
    print("▶ Khởi động Hệ Thống 2: Fintech & E-Wallet Service (:8020 - Node.js)...", flush=True)
    node_cmd = "node"
    p2 = subprocess.Popen(
        [node_cmd, "server.js"],
        cwd=str(FINTECH_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(p2)

    # 3. Start Hệ Thống 3 (Crawler Worker :8030)
    print("▶ Khởi động Hệ Thống 3: Autonomous Crawler Worker (:8030)...", flush=True)
    p3 = subprocess.Popen(
        [sys.executable, "worker.py"],
        cwd=str(CRAWLER_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(p3)

    print("\n⏳ Đang đợi 3 hệ thống khởi động và lắng nghe cổng...", flush=True)
    time.sleep(3.5)

    # Kiểm tra trạng thái
    s1_ok = is_port_online(SYS1_URL)
    s2_ok = is_port_online(SYS2_URL)
    s3_ok = is_port_online(SYS3_URL)
    hub_ok = is_port_online(HUB_URL)

    print(f"  • AgentGuard Hub (:8000)     : {'🟢 ONLINE' if hub_ok else '🔴 OFFLINE (Hãy chạy: uv run run.py)'}", flush=True)
    print(f"  • Hệ Thống 1 E-Commerce (:8010): {'🟢 ONLINE' if s1_ok else '🔴 FAILED'}", flush=True)
    print(f"  • Hệ Thống 2 Fintech (:8020)   : {'🟢 ONLINE (Node.js)' if s2_ok else '🔴 FAILED'}", flush=True)
    print(f"  • Hệ Thống 3 Crawler (:8030)   : {'🟢 ONLINE' if s3_ok else '🔴 FAILED'}", flush=True)


def trigger_live_demo():
    print("\n==================================================================", flush=True)
    print("🧪 GỬI CÁC REQUEST KIỂM THỬ THỰC TẾ VÀO CẢ 3 HỆ THỐNG AGENT", flush=True)
    print("==================================================================", flush=True)
    client = httpx.Client(timeout=10.0)

    # Test 1: Gửi vào E-Commerce (:8010)
    print("\n1️⃣ [GỬI VÀO HỆ THỐNG 1 :8010] Khách hỏi trạng thái đơn hàng #DH-1002:", flush=True)
    try:
        r1 = client.post(f"{SYS1_URL}/api/chat", json={
            "user_id": "cust_nguyen_99",
            "message": "Đơn hàng DH-1002 của tôi giao chưa shop ơi?",
            "order_id": "DH-1002"
        })
        d1 = r1.json()
        print(f"   👉 Phản hồi từ Agent: {d1.get('reply')[:75]}...", flush=True)
        print(f"   🏷️  Hub Run ID: {d1.get('hub_run_id')} (Trạng thái: COMPLETED)", flush=True)
    except Exception as e:
        print(f"   ❌ Lỗi: {e}", flush=True)

    time.sleep(1.0)

    # Test 2: Gửi vào Fintech (:8020)
    print("\n2️⃣ [GỬI VÀO HỆ THỐNG 2 :8020 - Node.js] Yêu cầu chuyển tiền 2.500.000₫ cho hóa đơn EVN:", flush=True)
    try:
        r2 = client.post(f"{SYS2_URL}/api/transfer", json={
            "account_id": "ACC-9988",
            "recipient": "EVN-ELECTRIC",
            "amount": 2500000
        })
        d2 = r2.json()
        print(f"   🛡️ Cảnh báo từ AgentGuard: {d2.get('message')}", flush=True)
        print(f"   🏷️  Hub Run ID: {d2.get('hub_run_id')} (Trạng thái: WAITING_APPROVAL)", flush=True)
    except Exception as e:
        print(f"   ❌ Lỗi: {e}", flush=True)

    time.sleep(1.0)

    # Test 3: Gửi vào Crawler Worker (:8030)
    print("\n3️⃣ [GỬI VÀO HỆ THỐNG 3 :8030] Kích hoạt cào dữ liệu gặp nút phân trang kẹt (Loop Trap):", flush=True)
    try:
        r3 = client.post(f"{SYS3_URL}/api/crawl/loop")
        d3 = r3.json()
        print(f"   🛡️ Chốt chặn kích hoạt: {d3.get('message')}", flush=True)
        print(f"   🏷️  Hub Run ID: {d3.get('hub_run_id')} (Trạng thái: TERMINATED_LOOP)", flush=True)
    except Exception as e:
        print(f"   ❌ Lỗi: {e}", flush=True)

    print("\n==================================================================", flush=True)
    print("🎉 TẤT CẢ DỮ LIỆU ĐÃ ĐƯỢC 3 HỆ THỐNG BẮN REALTIME LÊN AGENTGUARD!", flush=True)
    print("👉 Mở ngay Dashboard để quan sát: http://localhost:8000/dashboard (Gạt sang Live Mode)", flush=True)
    print("==================================================================", flush=True)


def stop_services():
    print("\n🛑 Đang dừng 3 hệ thống vệ tinh...", flush=True)
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("✅ Đã tắt toàn bộ các hệ thống an toàn.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Mock Host Systems Orchestrator")
    parser.add_argument("--test", action="store_true", help="Run test suite and exit cleanly")
    parser.add_argument("--daemon", action="store_true", help="Keep services running in background")
    args = parser.parse_args()

    start_services()

    try:
        trigger_live_demo()
        
        if args.daemon:
            print("\n⚡ Các hệ thống đang chạy nền (:8010, :8020, :8030). Bấm Ctrl+C để dừng...", flush=True)
            while True:
                time.sleep(1)
        else:
            print("\n✅ Hoàn tất kiểm thử tự động 3 hệ thống mẫu.", flush=True)
            stop_services()
    except KeyboardInterrupt:
        stop_services()


if __name__ == "__main__":
    main()
