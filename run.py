import os
import sys
from pathlib import Path
import uvicorn

os.environ["PYTHONUTF8"] = "1"

# Configure utf-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path so app can be imported cleanly
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings


def main():
    print(f"[*] Starting Agent Management System on http://{settings.APP_HOST}:{settings.APP_PORT}")
    print(f"[*] Dashboard available at: http://localhost:{settings.APP_PORT}/dashboard")
    print(f"[*] Swagger API Docs at:    http://localhost:{settings.APP_PORT}/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        reload_dirs=[str(backend_dir)] if settings.DEBUG else None
    )


if __name__ == "__main__":
    main()
