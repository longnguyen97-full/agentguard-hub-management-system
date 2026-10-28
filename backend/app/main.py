from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.api.routes import router as agent_router

app = FastAPI(
    title="Agent Observability & Management System",
    description="Enterprise Multi-Agent monitoring platform integrating Langfuse tracing, loop guardrails, budget limits, and Human-in-the-Loop approval workflows.",
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

# Template setup
templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)))

# Mount API routes
app.include_router(agent_router)


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the real-time Agent Monitoring & Control dashboard."""
    template = jinja_env.get_template("dashboard.html")
    return HTMLResponse(content=template.render())


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "langfuse_host": settings.LANGFUSE_HOST,
        "debug": settings.DEBUG,
    }

