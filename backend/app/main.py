from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.api.routes import router as agent_router
from app.core.otlp import process_otlp_trace_payload
from app.core.auth import verify_api_key

app = FastAPI(
    title="AgentGuard",
    description="Enterprise AI Agent Control Plane, Safety Guardrails & Tracing Hub.",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for assets (logos, icons)
assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# Template setup
templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)))

# Mount API routes
app.include_router(agent_router)


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the real-time AgentGuard Monitoring & Control dashboard."""
    template = jinja_env.get_template("dashboard.html")
    return HTMLResponse(content=template.render())


@app.get("/guide", response_class=HTMLResponse)
async def serve_user_guide(request: Request):
    """Serves the interactive user guide & developer integration manual."""
    template = jinja_env.get_template("guide.html")
    return HTMLResponse(content=template.render())


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    icon_path = assets_dir / "logo-icon.svg"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/svg+xml")
    return HTMLResponse(status_code=204)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "system": "AgentGuard",
        "simulation_mode": settings.SIMULATION_MODE,
        "langfuse_host": settings.LANGFUSE_HOST,
        "debug": settings.DEBUG,
    }


@app.post("/v1/traces")
@app.post("/api/otlp/v1/traces")
async def receive_otlp_traces(request: Request, _api_key: Optional[str] = Depends(verify_api_key)):
    """Receives and processes standard OpenTelemetry trace spans (OTLP/HTTP JSON)."""
    try:
        payload = await request.json()
        result = process_otlp_trace_payload(payload)
        return result
    except Exception as e:
        return {"partialSuccess": {"errorMessage": str(e)}}
