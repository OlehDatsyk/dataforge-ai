"""
DataForge AI - AI Analyst endpoints: insights, chart explanation, cleaning suggestions.
All operate on verified statistics computed by the deterministic analysis engine.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnalysisRun
from backend.schemas import InsightsRequest, ExplainChartRequest
from backend.services.profiling import build_profile
from backend.services.analysis import descriptive_stats, correlation_analysis, AnalysisError
from backend.services.charts import build_chart
from backend.dataset_utils import get_dataset_or_404, load_working_df
from backend.ai.manager import ai_manager

router = APIRouter(prefix="/api/datasets", tags=["ai"])


@router.post("/{dataset_id}/insights")
async def ai_insights(dataset_id: str, request: InsightsRequest, db: Session = Depends(get_db)):
    """Full AI Data Analyst report, grounded in a verified statistics bundle."""
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)

    profile = build_profile(df)
    stats = descriptive_stats(df)
    corr = correlation_analysis(df, threshold=0.5)

    verified_statistics = {
        "dataset_name": dataset.original_filename,
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "numeric_columns": profile["numeric_columns"],
        "text_columns": profile["text_columns"],
        "date_columns": profile["date_columns"],
        "duplicate_rows": profile["duplicate_rows"],
        "total_missing_values": profile["total_missing_values"],
        "descriptive_statistics": stats["statistics"],
        "strong_positive_correlations": corr["strong_positive"][:10],
        "strong_negative_correlations": corr["strong_negative"][:10],
    }

    envelope = await ai_manager.execute(
        operation="interpret_analysis", method_name="interpret_analysis",
        kwargs={"verified_statistics": verified_statistics, "focus": request.focus},
        requested_provider=request.provider, db=db,
    )

    response = {"verified_statistics": verified_statistics, "ai_result": envelope}
    db.add(AnalysisRun(
        dataset_id=dataset.id, analysis_type="insights", parameters_json=request.model_dump(),
        result_json=response, ai_provider=envelope.get("provider_used"),
        processing_time_ms=round((time.perf_counter() - start) * 1000, 1),
    ))
    db.commit()
    return response


@router.post("/{dataset_id}/business-insights")
async def business_insights(dataset_id: str, request: InsightsRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    profile = build_profile(df)
    stats = descriptive_stats(df)
    corr = correlation_analysis(df, threshold=0.5)
    verified_statistics = {
        "dataset_name": dataset.original_filename,
        "profile_summary": {
            "row_count": profile["row_count"], "column_count": profile["column_count"],
            "duplicate_rows": profile["duplicate_rows"], "total_missing_values": profile["total_missing_values"],
        },
        "descriptive_statistics": stats["statistics"],
        "strong_positive_correlations": corr["strong_positive"][:10],
        "strong_negative_correlations": corr["strong_negative"][:10],
    }
    envelope = await ai_manager.execute(
        operation="generate_business_insights", method_name="generate_business_insights",
        kwargs={"verified_statistics": verified_statistics}, requested_provider=request.provider, db=db,
    )
    response = {"verified_statistics": verified_statistics, "ai_result": envelope}
    db.add(AnalysisRun(
        dataset_id=dataset.id, analysis_type="business_insights", parameters_json=request.model_dump(),
        result_json=response, ai_provider=envelope.get("provider_used"),
        processing_time_ms=round((time.perf_counter() - start) * 1000, 1),
    ))
    db.commit()
    return response


@router.post("/{dataset_id}/explain")
async def explain_chart(dataset_id: str, request: ExplainChartRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        chart_data = request.chart_data or build_chart(
            df, request.chart_type, request.x, request.y, request.aggregation, request.group_by,
        )
    except AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))

    chart_context = {
        "chart_type": request.chart_type, "x_axis": request.x, "y_axis": request.y,
        "aggregation": request.aggregation, "group_by": request.group_by,
        "labels": chart_data.get("labels"), "datasets": chart_data.get("datasets"),
    }
    envelope = await ai_manager.execute(
        operation="explain_chart", method_name="explain_chart",
        kwargs={"chart_context": chart_context}, requested_provider=request.provider, db=db,
    )
    response = {"chart_data": chart_data, "ai_result": envelope}
    db.add(AnalysisRun(
        dataset_id=dataset.id, analysis_type="explain_chart", parameters_json=request.model_dump(),
        result_json=response, ai_provider=envelope.get("provider_used"),
        processing_time_ms=round((time.perf_counter() - start) * 1000, 1),
    ))
    db.commit()
    return response


@router.post("/{dataset_id}/cleaning-suggestions")
async def cleaning_suggestions(dataset_id: str, request: InsightsRequest, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    profile = build_profile(df)
    envelope = await ai_manager.execute(
        operation="suggest_cleaning_steps", method_name="suggest_cleaning_steps",
        kwargs={"profile": profile}, requested_provider=request.provider, db=db,
    )
    return {"profile_summary": {"row_count": profile["row_count"], "column_count": profile["column_count"]},
            "ai_result": envelope}
