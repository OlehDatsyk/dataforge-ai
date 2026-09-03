"""DataForge AI - Dataset upload, retrieval, cleaning, and export endpoints."""
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Dataset, DatasetProfile, CleaningOperation
from backend.schemas import CleanOperationRequest
from backend.security import validate_extension, validate_size, generate_stored_name
from backend.services.data_loader import load_dataframe, save_dataframe, DataLoadError
from backend.services.profiling import build_profile, sample_rows, detect_column_types, _clean_scalar
from backend.services.cleaning import apply_operation
from backend.services.analysis import AnalysisError
from backend.dataset_utils import get_dataset_or_404, working_path, original_path, load_working_df

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    try:
        ext = validate_extension(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    content = await file.read()
    try:
        validate_size(len(content))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stored_name = generate_stored_name(file.filename)
    upload_path = settings.UPLOADS_DIR / stored_name
    with open(upload_path, "wb") as f:
        f.write(content)

    file_type = ext.lstrip(".")
    try:
        df = load_dataframe(upload_path, file_type)
    except DataLoadError as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    working_name = stored_name.rsplit(".", 1)[0] + ".csv"
    save_dataframe(df, settings.WORKING_DIR / working_name)

    col_types = detect_column_types(df)
    dataset = Dataset(
        original_filename=file.filename,
        stored_filename=stored_name,
        working_filename=working_name,
        file_type=file_type,
        file_size_bytes=len(content),
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        columns_json=list(df.columns),
        dtypes_json=col_types,
        status="ready",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    profile = build_profile(df)
    db.add(DatasetProfile(dataset_id=dataset.id, profile_json=profile))
    db.commit()

    return {
        "id": dataset.id,
        "original_filename": dataset.original_filename,
        "file_type": dataset.file_type,
        "file_size_bytes": dataset.file_size_bytes,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "columns": dataset.columns_json,
        "dtypes": dataset.dtypes_json,
        "status": dataset.status,
        "sample_rows": sample_rows(df, settings.PREVIEW_ROWS),
        "profile": profile,
    }


@router.get("")
def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return [
        {
            "id": d.id, "original_filename": d.original_filename, "file_type": d.file_type,
            "row_count": d.row_count, "column_count": d.column_count,
            "file_size_bytes": d.file_size_bytes, "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    return {
        "id": dataset.id, "original_filename": dataset.original_filename, "file_type": dataset.file_type,
        "file_size_bytes": dataset.file_size_bytes, "row_count": int(df.shape[0]), "column_count": int(df.shape[1]),
        "columns": list(df.columns), "dtypes": detect_column_types(df), "status": dataset.status,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "sample_rows": sample_rows(df, settings.PREVIEW_ROWS),
    }


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    working_path(dataset).unlink(missing_ok=True)
    original_path(dataset).unlink(missing_ok=True)
    db.delete(dataset)
    db.commit()
    return {"success": True, "message": "Dataset deleted."}


@router.get("/{dataset_id}/profile")
def get_profile(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    profile = build_profile(df)
    db.add(DatasetProfile(dataset_id=dataset.id, profile_json=profile))
    db.commit()
    return profile


@router.post("/{dataset_id}/clean")
def clean_dataset(dataset_id: str, request: CleanOperationRequest, db: Session = Depends(get_db)):
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Cleaning operations require explicit confirmation (confirm=true).")
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    try:
        new_df, info = apply_operation(df, request.operation, request.column, request.params)
    except AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))

    save_dataframe(new_df, working_path(dataset))
    dataset.row_count = int(new_df.shape[0])
    dataset.column_count = int(new_df.shape[1])
    dataset.columns_json = list(new_df.columns)
    dataset.dtypes_json = detect_column_types(new_df)
    db.add(dataset)

    op_record = CleaningOperation(
        dataset_id=dataset.id, operation=request.operation, column=request.column,
        params_json=request.params, rows_before=info["rows_before"], rows_after=info["rows_after"],
        columns_before=info["columns_before"], columns_after=info["columns_after"],
    )
    db.add(op_record)
    db.commit()

    return {
        "success": True, "operation": request.operation, "rows_before": info["rows_before"],
        "rows_after": info["rows_after"], "rows_affected": info["rows_affected"],
        "columns_after": info["columns_after"], "extra": {k: v for k, v in info.items() if k.startswith("fill_value")},
        "sample_rows": sample_rows(new_df, settings.PREVIEW_ROWS),
    }


@router.post("/{dataset_id}/reset")
def reset_dataset(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    try:
        df = load_dataframe(original_path(dataset), dataset.file_type)
    except DataLoadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    save_dataframe(df, working_path(dataset))
    dataset.row_count = int(df.shape[0])
    dataset.column_count = int(df.shape[1])
    dataset.columns_json = list(df.columns)
    dataset.dtypes_json = detect_column_types(df)
    db.add(dataset)
    db.commit()
    return {"success": True, "message": "Working dataset reset to the original upload.",
            "row_count": dataset.row_count, "column_count": dataset.column_count}


@router.get("/{dataset_id}/cleaning-history")
def cleaning_history(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    ops = (db.query(CleaningOperation)
           .filter(CleaningOperation.dataset_id == dataset.id)
           .order_by(CleaningOperation.created_at.asc()).all())
    return [
        {
            "id": o.id, "operation": o.operation, "column": o.column, "params": o.params_json,
            "rows_before": o.rows_before, "rows_after": o.rows_after,
            "rows_affected": abs(o.rows_after - o.rows_before),
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in ops
    ]


@router.get("/{dataset_id}/export/csv")
def export_csv(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    path = working_path(dataset)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Working dataset file missing.")
    filename = Path(dataset.original_filename).stem + "_cleaned.csv"
    return FileResponse(path, media_type="text/csv", filename=filename)


@router.get("/{dataset_id}/export/xlsx")
def export_xlsx(dataset_id: str, db: Session = Depends(get_db)):
    dataset = get_dataset_or_404(db, dataset_id)
    df = load_working_df(dataset)
    out_path = settings.WORKING_DIR / f"{dataset.id}_export.xlsx"
    df.to_excel(out_path, index=False, engine="openpyxl")
    filename = Path(dataset.original_filename).stem + "_cleaned.xlsx"
    return FileResponse(out_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         filename=filename)
