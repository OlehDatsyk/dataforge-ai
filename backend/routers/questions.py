"""
DataForge AI - "Ask Your Data" endpoint.
Question -> safe query engine (deterministic calculation) -> optional AI explanation.
The AI is only ever asked to explain the number that was already calculated.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnalysisRun
from backend.schemas import AskRequest
from backend.services.query_engine import answer_question, QueryEngineError
from backend.dataset_utils import get_dataset_or_404, load_working_df
from backend.ai.manager import ai_manager

router = APIRouter(prefix="/api/datasets", tags=["questions"])


@router.post("/{dataset_id}/ask")
async def ask_data(dataset_id: str, request: AskRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        calc_result = answer_question(df, request.question)
    except QueryEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))

    envelope = await ai_manager.execute(
        operation="answer_data_question",
        method_name="answer_data_question",
        kwargs={"question": request.question, "query_result": calc_result},
        requested_provider=request.provider,
        db=db,
    )

    response = {
        "question": request.question,
        "calculated_result": calc_result,
        "ai_explanation": envelope,
    }
    db.add(AnalysisRun(
        dataset_id=dataset.id, analysis_type="ask", parameters_json={"question": request.question},
        result_json=response, ai_provider=envelope.get("provider_used"),
        processing_time_ms=round((time.perf_counter() - start) * 1000, 1),
    ))
    db.commit()
    return response
