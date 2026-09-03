"""
DataForge AI - Data loading utilities.
Loads CSV / TSV / Excel / JSON safely into pandas DataFrames, with
validation for corrupted files, empty datasets, and row limits.
"""
import json
from pathlib import Path

import pandas as pd

from backend.config import settings


class DataLoadError(ValueError):
    pass


def load_dataframe(path: Path, file_type: str) -> pd.DataFrame:
    """Load a dataframe from disk. Raises DataLoadError with a clear message on failure."""
    try:
        if file_type == "csv":
            df = pd.read_csv(path, low_memory=False)
        elif file_type == "tsv":
            df = pd.read_csv(path, sep="\t", low_memory=False)
        elif file_type in ("xlsx", "xls"):
            df = pd.read_excel(path, engine="openpyxl" if file_type == "xlsx" else None)
        elif file_type == "json":
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            df = _json_to_dataframe(raw)
        else:
            raise DataLoadError(f"Unsupported file type: {file_type}")
    except DataLoadError:
        raise
    except pd.errors.EmptyDataError:
        raise DataLoadError("The uploaded file has no readable data.")
    except pd.errors.ParserError as e:
        raise DataLoadError(f"The file appears to be corrupted or malformed: {e}")
    except ValueError as e:
        raise DataLoadError(f"Could not parse file: {e}")
    except Exception as e:  # noqa: BLE001 - surface as a controlled error, never crash
        raise DataLoadError(f"Failed to load file: {e}")

    if df is None or df.shape[0] == 0 or df.shape[1] == 0:
        raise DataLoadError("The dataset is empty or contains no tabular data.")

    if df.shape[0] > settings.MAX_ROWS:
        raise DataLoadError(
            f"Dataset has {df.shape[0]:,} rows, exceeding the configured limit of "
            f"{settings.MAX_ROWS:,} rows (MAX_ROWS). Please upload a smaller file or "
            f"increase MAX_ROWS in your environment configuration."
        )

    # Normalise column names to strings (handles numeric/mixed headers safely)
    df.columns = [str(c) for c in df.columns]
    return df


def _json_to_dataframe(raw) -> pd.DataFrame:
    """Convert tabular-ish JSON (list of records, or {col: [values]}) into a DataFrame."""
    if isinstance(raw, list):
        if not raw:
            raise DataLoadError("The JSON file contains an empty list.")
        if not all(isinstance(r, dict) for r in raw):
            raise DataLoadError("JSON must be a list of objects (records) to be treated as tabular data.")
        return pd.json_normalize(raw)
    if isinstance(raw, dict):
        # {"data": [...]} wrapper support
        if "data" in raw and isinstance(raw["data"], list):
            return _json_to_dataframe(raw["data"])
        # column-oriented dict: {"col1": [...], "col2": [...]}
        if all(isinstance(v, list) for v in raw.values()):
            try:
                return pd.DataFrame(raw)
            except ValueError as e:
                raise DataLoadError(f"JSON columns have mismatched lengths: {e}")
        raise DataLoadError(
            "JSON structure not recognised as tabular data. Expected a list of objects "
            "or a dict of column-arrays."
        )
    raise DataLoadError("JSON root must be an object or a list.")


def save_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Persist the working dataframe to disk as CSV (canonical working format)."""
    df.to_csv(path, index=False)


def read_working_dataframe(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c) for c in df.columns]
    return df
