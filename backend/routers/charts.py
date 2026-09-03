"""DataForge AI - Chart data endpoint."""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnalysisRun
from backend.schemas import ChartRequest
from backend.services.charts import build_chart
from backend.services.analysis import AnalysisError
from backend.dataset_utils import get_dataset_or_404, load_working_df

router = APIRouter(prefix="/api/datasets", tags=["charts"])


@router.post("/{dataset_id}/chart")
def create_chart(dataset_id: str, request: ChartRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        result = build_chart(df, request.chart_type, request.x, request.y,
                              request.aggregation, request.group_by, request.bins)
    except AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.add(AnalysisRun(
        dataset_id=dataset.id, analysis_type="chart", parameters_json=request.model_dump(),
        result_json=result, processing_time_ms=round((time.perf_counter() - start) * 1000, 1),
    ))
    db.commit()
    return result
