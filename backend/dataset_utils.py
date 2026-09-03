"""
DataForge AI - Shared dataset helper functions used across routers.
Keeps disk-path resolution and dataframe loading logic in one place.
"""
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import Dataset
from backend.services.data_loader import read_working_dataframe


def get_dataset_or_404(db: Session, dataset_id: str) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


def working_path(dataset: Dataset) -> Path:
    return settings.WORKING_DIR / dataset.working_filename


def original_path(dataset: Dataset) -> Path:
    return settings.UPLOADS_DIR / dataset.stored_filename


def load_working_df(dataset: Dataset):
    path = working_path(dataset)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Working dataset file is missing on disk (it may have expired).")
    return read_working_dataframe(path)
