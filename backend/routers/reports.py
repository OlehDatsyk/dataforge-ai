"""DataForge AI - Report generation endpoints."""
import time
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Report
from backend.schemas import ReportGenerateRequest
from backend.services.profiling import build_profile
from backend.services.analysis import descriptive_stats, correlation_analysis, missing_value_analysis
from backend.services.reports import build_report_markdown, markdown_to_html, REPORT_TITLES
from backend.dataset_utils import get_dataset_or_404, load_working_df
from backend.ai.manager import ai_manager

router = APIRouter(tags=["reports"])


def _gather_stats(report_type: str, df) -> dict:
    profile = build_profile(df)
    base = {
        "row_count": profile["row_count"], "column_count": profile["column_count"],
        "numeric_columns": profile["numeric_columns"], "duplicate_rows": profile["duplicate_rows"],
        "total_missing_values": profile["total_missing_values"],
    }
    if report_type in ("dataset_profile", "executive_summary"):
        base["profile"] = profile
    if report_type in ("data_quality", "executive_summary"):
        base["missing_analysis"] = missing_value_analysis(df)
    if report_type in ("business_analysis", "trend", "executive_summary", "kpi"):
        base["descriptive_statistics"] = descriptive_stats(df)["statistics"]
        base["correlations"] = correlation_analysis(df, threshold=0.5)
    return base


@router.post("/api/reports/generate")
async def generate_report(request: ReportGenerateRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, request.dataset_id)
    df = load_working_df(dataset)

    stats = _gather_stats(request.report_type, df)

    ai_section = None
    provider_used = None
    if request.include_ai:
        envelope = await ai_manager.execute(
            operation="generate_report", method_name="generate_report",
            kwargs={"verified_statistics": stats, "report_type": request.report_type},
            requested_provider=request.provider, db=db,
        )
        if envelope.get("success"):
            ai_section = envelope.get("data")
            provider_used = envelope.get("provider_used")

    md = build_report_markdown(request.report_type, dataset.original_filename, stats, ai_section, provider_used)
    title = REPORT_TITLES.get(request.report_type, "DataForge AI Report")

    report = Report(
        dataset_id=dataset.id, report_type=request.report_type, title=title,
        content_markdown=md, content_json={"statistics": stats, "ai_section": ai_section},
        ai_provider=provider_used,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    fmt = request.export_format.lower()
    if fmt == "html":
        content = markdown_to_html(md, title)
        media_type, ext = "text/html", "html"
    elif fmt == "json":
        content = json.dumps({"title": title, "statistics": stats, "ai_section": ai_section,
                               "ai_provider": provider_used}, indent=2, default=str)
        media_type, ext = "application/json", "json"
    elif fmt == "txt":
        content = md
        media_type, ext = "text/plain", "txt"
    else:
        content = md
        media_type, ext = "text/markdown", "md"

    return {
        "report_id": report.id, "title": title, "ai_provider": provider_used,
        "export_format": fmt, "content": content, "media_type": media_type,
        "processing_time_ms": round((time.perf_counter() - start) * 1000, 1),
    }


@router.get("/api/reports")
def list_reports(db: Session = Depends(get_db)):
    reports = db.query(Report).order_by(Report.created_at.desc()).limit(200).all()
    return [
        {"id": r.id, "dataset_id": r.dataset_id, "report_type": r.report_type, "title": r.title,
         "ai_provider": r.ai_provider, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in reports
    ]


@router.get("/api/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return {
        "id": report.id, "dataset_id": report.dataset_id, "report_type": report.report_type,
        "title": report.title, "content_markdown": report.content_markdown,
        "content_json": report.content_json, "ai_provider": report.ai_provider,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
