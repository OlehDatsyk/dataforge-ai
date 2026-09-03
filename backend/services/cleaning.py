"""
DataForge AI - Data cleaning workspace operations.
Operates only on the WORKING copy of a dataset; the original upload is
never modified. Every operation returns before/after metrics for the
transformation history log.
"""
from __future__ import annotations
import pandas as pd

from backend.services.analysis import AnalysisError


ALLOWED_OPERATIONS = {
    "remove_duplicates", "drop_missing", "fill_missing_numeric",
    "fill_missing_categorical", "rename_column", "trim_whitespace",
    "standardize_case", "convert_dtype", "parse_dates",
}


def apply_operation(df: pd.DataFrame, operation: str, column: str | None, params: dict) -> tuple[pd.DataFrame, dict]:
    """Apply one cleaning operation to a copy of df. Returns (new_df, info)."""
    if operation not in ALLOWED_OPERATIONS:
        raise AnalysisError(f"Unknown cleaning operation '{operation}'.")

    work = df.copy()
    info = {"rows_before": int(work.shape[0]), "columns_before": list(work.columns)}

    if operation == "remove_duplicates":
        work = work.drop_duplicates()

    elif operation == "drop_missing":
        if column:
            if column not in work.columns:
                raise AnalysisError(f"Column '{column}' not found.")
            work = work.dropna(subset=[column])
        else:
            work = work.dropna()

    elif operation == "fill_missing_numeric":
        if not column or column not in work.columns:
            raise AnalysisError("A valid numeric column is required.")
        if not pd.api.types.is_numeric_dtype(work[column]):
            raise AnalysisError(f"Column '{column}' is not numeric.")
        strategy = params.get("strategy", "median")
        if strategy == "mean":
            fill_value = work[column].mean()
        elif strategy == "mode":
            m = work[column].mode()
            fill_value = m.iloc[0] if not m.empty else 0
        else:
            fill_value = work[column].median()
        work[column] = work[column].fillna(fill_value)
        info["fill_value"] = float(fill_value) if fill_value is not None else None

    elif operation == "fill_missing_categorical":
        if not column or column not in work.columns:
            raise AnalysisError("A valid column is required.")
        strategy = params.get("strategy", "mode")
        if strategy == "constant":
            fill_value = params.get("value", "Unknown")
        else:
            m = work[column].mode()
            fill_value = m.iloc[0] if not m.empty else "Unknown"
        work[column] = work[column].fillna(fill_value)
        info["fill_value"] = str(fill_value)

    elif operation == "rename_column":
        new_name = params.get("new_name")
        if not column or column not in work.columns:
            raise AnalysisError("A valid existing column is required.")
        if not new_name:
            raise AnalysisError("A new_name parameter is required.")
        work = work.rename(columns={column: new_name})

    elif operation == "trim_whitespace":
        cols = [column] if column else work.select_dtypes(include="object").columns.tolist()
        for c in cols:
            if c in work.columns and work[c].dtype == object:
                work[c] = work[c].astype(str).str.strip()

    elif operation == "standardize_case":
        if not column or column not in work.columns:
            raise AnalysisError("A valid column is required.")
        case = params.get("case", "lower")
        if case == "upper":
            work[column] = work[column].astype(str).str.upper()
        elif case == "title":
            work[column] = work[column].astype(str).str.title()
        else:
            work[column] = work[column].astype(str).str.lower()

    elif operation == "convert_dtype":
        if not column or column not in work.columns:
            raise AnalysisError("A valid column is required.")
        target = params.get("target_type", "string")
        try:
            if target == "numeric":
                work[column] = pd.to_numeric(work[column], errors="coerce")
            elif target == "string":
                work[column] = work[column].astype(str)
            elif target == "boolean":
                work[column] = work[column].astype(str).str.lower().isin(["true", "1", "yes", "y"])
            else:
                raise AnalysisError(f"Unsupported target_type '{target}'.")
        except (ValueError, TypeError) as e:
            raise AnalysisError(f"Could not convert column '{column}' to {target}: {e}")

    elif operation == "parse_dates":
        if not column or column not in work.columns:
            raise AnalysisError("A valid column is required.")
        work[column] = pd.to_datetime(work[column], errors="coerce", format="mixed")

    info["rows_after"] = int(work.shape[0])
    info["columns_after"] = list(work.columns)
    info["rows_affected"] = abs(info["rows_after"] - info["rows_before"])
    return work, info
