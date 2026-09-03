"""DataForge AI - Deterministic analysis endpoints (descriptive, missing, outliers, correlation, group, timeseries, kpi, category)."""
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnalysisRun
from backend.schemas import (
    GroupAnalysisRequest, CorrelationRequest, OutlierRequest, TimeSeriesRequest, KPIRequest,
)
from backend.services import analysis as A
from backend.dataset_utils import get_dataset_or_404, load_working_df

router = APIRouter(prefix="/api/datasets", tags=["analysis"])


def _record_run(db: Session, dataset_id: str, analysis_type: str, params: dict, result: dict, start: float):
    run = AnalysisRun(
        dataset_id=dataset_id, analysis_type=analysis_type, parameters_json=params,
        result_json=result, processing_time_ms=round((time.perf_counter() - start) * 1000, 1),
    )
    db.add(run)
    db.commit()
    return run


@router.post("/{dataset_id}/analyze/descriptive")
def descriptive(dataset_id: str, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    result = A.descriptive_stats(df)
    _record_run(db, dataset.id, "descriptive", {}, result, start)
    return result


@router.post("/{dataset_id}/analyze/missing")
def missing(dataset_id: str, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    result = A.missing_value_analysis(df)
    _record_run(db, dataset.id, "missing", {}, result, start)
    return result


@router.post("/{dataset_id}/analyze/duplicates")
def duplicates(dataset_id: str, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    result = A.duplicate_analysis(df)
    _record_run(db, dataset.id, "duplicates", {}, result, start)
    return result


@router.post("/{dataset_id}/analyze/outliers")
def outliers(dataset_id: str, request: OutlierRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        result = A.outlier_analysis(df, request.method, request.threshold, request.columns)
    except A.AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _record_run(db, dataset.id, "outliers", request.model_dump(), result, start)
    return result


@router.post("/{dataset_id}/analyze/correlation")
def correlation(dataset_id: str, request: CorrelationRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    result = A.correlation_analysis(df, request.threshold, request.method)
    _record_run(db, dataset.id, "correlation", request.model_dump(), result, start)
    return result


@router.post("/{dataset_id}/analyze/group")
def group(dataset_id: str, request: GroupAnalysisRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        result = A.grouped_analysis(df, request.group_by, request.metric, request.aggregation)
    except A.AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _record_run(db, dataset.id, "group", request.model_dump(), result, start)
    return result


@router.post("/{dataset_id}/analyze/timeseries")
def timeseries(dataset_id: str, request: TimeSeriesRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        result = A.timeseries_analysis(df, request.date_column, request.value_column,
                                        request.frequency, request.aggregation)
    except A.AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _record_run(db, dataset.id, "timeseries", request.model_dump(), result, start)
    return result


@router.post("/{dataset_id}/analyze/kpi")
def kpi(dataset_id: str, request: KPIRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        result = A.kpi_analysis(df, request.metric_column, request.aggregation, request.group_by, request.target)
    except A.AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _record_run(db, dataset.id, "kpi", request.model_dump(), result, start)
    return result


@router.get("/{dataset_id}/analyze/category")
def category(dataset_id: str, column: str = Query(...), top_n: int = Query(15), db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        result = A.category_analysis(df, column, top_n)
    except A.AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _record_run(db, dataset.id, "category", {"column": column, "top_n": top_n}, result, start)
    return result
