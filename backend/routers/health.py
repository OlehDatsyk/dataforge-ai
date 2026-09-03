"""DataForge AI - Health & dashboard-stats endpoints. No AI call is ever made here."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models import Dataset, Report, AnalysisRun, CleaningOperation, AILog
from backend.config import settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "subtitle": settings.APP_SUBTITLE,
    }


@router.get("/api/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    datasets_analysed = db.query(func.count(Dataset.id)).scalar() or 0
    rows_processed = db.query(func.coalesce(func.sum(Dataset.row_count), 0)).scalar() or 0
    reports_generated = db.query(func.count(Report.id)).scalar() or 0
    ai_analyses = db.query(func.count(AnalysisRun.id)).filter(
        AnalysisRun.analysis_type.in_(["insights", "business_insights", "ask", "explain_chart"])
    ).scalar() or 0
    cleaning_operations = db.query(func.count(CleaningOperation.id)).scalar() or 0
    charts_generated = db.query(func.count(AnalysisRun.id)).filter(AnalysisRun.analysis_type == "chart").scalar() or 0
    provider_fallbacks = db.query(func.count(AILog.id)).filter(AILog.fallback_used == True).scalar() or 0  # noqa: E712

    return {
        "datasets_analysed": datasets_analysed,
        "rows_processed": int(rows_processed),
        "reports_generated": reports_generated,
        "ai_analyses": ai_analyses,
        "cleaning_operations": cleaning_operations,
        "charts_generated": charts_generated,
        "provider_fallbacks": provider_fallbacks,
    }
