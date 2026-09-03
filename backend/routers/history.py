"""DataForge AI - Analysis history endpoints (view / delete / re-run / export)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnalysisRun

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(dataset_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    if dataset_id:
        query = query.filter(AnalysisRun.dataset_id == dataset_id)
    runs = query.limit(300).all()
    return [
        {
            "id": r.id, "dataset_id": r.dataset_id, "analysis_type": r.analysis_type,
            "parameters": r.parameters_json, "ai_provider": r.ai_provider,
            "processing_time_ms": r.processing_time_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.get("/{run_id}")
def get_history_item(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return {
        "id": run.id, "dataset_id": run.dataset_id, "analysis_type": run.analysis_type,
        "parameters": run.parameters_json, "result": run.result_json, "ai_provider": run.ai_provider,
        "processing_time_ms": run.processing_time_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.delete("/{run_id}")
def delete_history_item(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    db.delete(run)
    db.commit()
    return {"success": True}


@router.get("/{run_id}/export")
def export_history_item(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    payload = {
        "id": run.id, "dataset_id": run.dataset_id, "analysis_type": run.analysis_type,
        "parameters": run.parameters_json, "result": run.result_json, "ai_provider": run.ai_provider,
        "processing_time_ms": run.processing_time_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
    return Response(content=json.dumps(payload, indent=2, default=str), media_type="application/json",
                     headers={"Content-Disposition": f"attachment; filename=analysis_{run.id}.json"})
