"""
DataForge AI - AI-Powered Data Analysis, Insights & Reporting Platform
Built by Oleh Datsyk

Entry point. Run locally with:
    uvicorn app:app --host 127.0.0.1 --port 8000 --reload
On Render:
    uvicorn app:app --host 0.0.0.0 --port $PORT
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.database import init_db
from backend.routers import health, datasets, analysis, charts, questions, ai, reports, history, providers

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_SUBTITLE,
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health.router)
app.include_router(datasets.router)
app.include_router(analysis.router)
app.include_router(charts.router)
app.include_router(questions.router)
app.include_router(ai.router)
app.include_router(reports.router)
app.include_router(history.router)
app.include_router(providers.router)

# --- Frontend static files ---
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
