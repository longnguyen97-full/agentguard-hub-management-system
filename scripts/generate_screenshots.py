import time
import httpx
from pathlib import Path
from playwright.sync_api import sync_playwright

API_BASE = "http://localhost:8000"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
browser_path = EDGE_PATH if Path(EDGE_PATH).exists() else CHROME_PATH

client = httpx.Client(base_url=API_BASE, timeout=20.0)

def seed_runs():
    print("[+] Seeding test scenarios via API...")
    
    # 1. Standard run
    r1 = client.post("/api/agents/run", json={"prompt": "Search knowledge base and calculate system latency metrics"})
    print("  -> Started standard run:", r1.json()["run_id"])
    time.sleep(3.5)  # Wait for it to complete 3 steps

    # 2. Infinite Loop run
    r2 = client.post("/api/agents/run", json={"prompt": "Simulate infinite loop by calling check_health repetitively"})
    print("  -> Started loop run:", r2.json()["run_id"])
    time.sleep(3.5)  # Wait for guardrail to catch loop

    # 3. Human in the loop run (leave it waiting approval)
    r3 = client.post("/api/agents/run", json={"prompt": "Update user quota in production database with sensitive record"})
    approval_run_id = r3.json()["run_id"]
    print("  -> Started approval run:", approval_run_id)
    time.sleep(2.5)  # Wait for it to pause at WAITING_APPROVAL

    return {
        "standard": r1.json()["run_id"],
        "loop": r2.json()["run_id"],
        "approval": approval_run_id
    }

def capture_all():
    run_ids = seed_runs()
    
    print(f"[+] Launching browser ({browser_path})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--no-sandbox", "--disable-gpu"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        
        # Navigate to Dashboard
        print("[+] Opening http://localhost:8000/dashboard...")
        page.goto(f"{API_BASE}/dashboard", wait_until="networkidle")
        time.sleep(1.5)

        # 1. Capture Dashboard Overview (English default, standard run selected)
        print("  -> Capturing assets/dashboard-overview.png...")
        page.evaluate(f"selectRun('{run_ids['standard']}')")
        time.sleep(1.0)
        page.screenshot(path=str(ASSETS_DIR / "dashboard-overview.png"))

        # 2. Capture Human-in-the-Loop Approval
        print("  -> Capturing assets/human-in-the-loop.png...")
        page.evaluate(f"selectRun('{run_ids['approval']}')")
        time.sleep(1.0)
        page.screenshot(path=str(ASSETS_DIR / "human-in-the-loop.png"))

        # 3. Capture Loop Guardrail
        print("  -> Capturing assets/loop-guardrail.png...")
        page.evaluate(f"selectRun('{run_ids['loop']}')")
        time.sleep(1.0)
        page.screenshot(path=str(ASSETS_DIR / "loop-guardrail.png"))

        # 4. Capture Vietnamese Mode (VND currency)
        print("  -> Capturing assets/vietnamese-mode.png...")
        page.evaluate("setLanguage('vi')")
        time.sleep(1.0)
        page.screenshot(path=str(ASSETS_DIR / "vietnamese-mode.png"))

        browser.close()
    
    print("[OK] All screenshots saved successfully in assets/!")

if __name__ == "__main__":
    capture_all()
