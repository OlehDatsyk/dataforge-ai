"""
DataForge AI - Deterministic analysis engine.
Every function here performs a real pandas/numpy calculation and returns
verified numbers. AI is never used to produce these values - it may only
be asked to *explain* them afterwards (see backend/ai/).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from backend.services.profiling import detect_column_types, _clean_scalar


class AnalysisError(ValueError):
    pass


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    types = detect_column_types(df)
    return [c for c, t in types.items() if t == "numeric"]


def _require_column(df: pd.DataFrame, col: str):
    if col not in df.columns:
        raise AnalysisError(f"Column '{col}' does not exist in this dataset.")


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def descriptive_stats(df: pd.DataFrame) -> dict:
    numeric_cols = _numeric_columns(df)
    result = {}
    for col in numeric_cols:
        s = df[col].astype(float)
        result[col] = {
            "count": int(s.notna().sum()),
            "mean": _clean_scalar(s.mean()),
            "median": _clean_scalar(s.median()),
            "min": _clean_scalar(s.min()),
            "max": _clean_scalar(s.max()),
            "std": _clean_scalar(s.std()),
            "sum": _clean_scalar(s.sum()),
            "p25": _clean_scalar(s.quantile(0.25)),
            "p75": _clean_scalar(s.quantile(0.75)),
        }
    return {"numeric_columns": numeric_cols, "statistics": result, "row_count": int(df.shape[0])}


# ---------------------------------------------------------------------------
# Missing values
# ---------------------------------------------------------------------------

def missing_value_analysis(df: pd.DataFrame) -> dict:
    n = df.shape[0]
    rows = []
    for col in df.columns:
        missing = int(df[col].isna().sum())
        pct = round((missing / n) * 100, 2) if n else 0.0
        recommendation = "leave_unchanged"
        if pct == 0:
            recommendation = "leave_unchanged"
        elif pct < 5:
            recommendation = "fill_median" if pd.api.types.is_numeric_dtype(df[col]) else "fill_mode"
        elif pct < 40:
            recommendation = "fill_median" if pd.api.types.is_numeric_dtype(df[col]) else "fill_mode"
        else:
            recommendation = "consider_drop_column"
        rows.append({
            "column": col,
            "missing_count": missing,
            "missing_pct": pct,
            "recommendation": recommendation,
        })
    rows.sort(key=lambda r: r["missing_pct"], reverse=True)
    return {
        "columns": rows,
        "total_missing": int(df.isna().sum().sum()),
        "note": "Recommendations are suggestions only. No data is modified automatically.",
    }


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------

def duplicate_analysis(df: pd.DataFrame, preview_n: int = 10) -> dict:
    n = df.shape[0]
    dup_mask = df.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    preview = df[df.duplicated(keep=False)].head(preview_n)
    preview_records = preview.to_dict(orient="records") if not preview.empty else []
    preview_records = [{k: _clean_scalar(v) for k, v in r.items()} for r in preview_records]
    return {
        "duplicate_count": dup_count,
        "duplicate_pct": round((dup_count / n) * 100, 2) if n else 0.0,
        "preview": preview_records,
    }


# ---------------------------------------------------------------------------
# Outliers (IQR / Z-score) - deterministic
# ---------------------------------------------------------------------------

def outlier_analysis(df: pd.DataFrame, method: str = "iqr", threshold: float = 1.5,
                      columns: list[str] | None = None) -> dict:
    numeric_cols = columns or _numeric_columns(df)
    numeric_cols = [c for c in numeric_cols if c in df.columns]
    results = []
    for col in numeric_cols:
        s = df[col].dropna().astype(float)
        if len(s) == 0:
            continue
        if method == "zscore":
            mean, std = s.mean(), s.std()
            if std == 0 or np.isnan(std):
                outliers = pd.Series([], dtype=float)
            else:
                z = (s - mean) / std
                outliers = s[z.abs() > threshold]
            lower_bound, upper_bound = _clean_scalar(mean - threshold * std) if std else None, \
                _clean_scalar(mean + threshold * std) if std else None
        else:  # iqr
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            outliers = s[(s < lower_bound) | (s > upper_bound)]
            lower_bound, upper_bound = _clean_scalar(lower_bound), _clean_scalar(upper_bound)

        results.append({
            "column": col,
            "method": method,
            "threshold": threshold,
            "outlier_count": int(len(outliers)),
            "outlier_pct": round((len(outliers) / len(s)) * 100, 2) if len(s) else 0.0,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "example_values": [_clean_scalar(v) for v in outliers.head(5).tolist()],
        })
    return {"method": method, "threshold": threshold, "results": results}


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def correlation_analysis(df: pd.DataFrame, threshold: float = 0.5, method: str = "pearson") -> dict:
    numeric_cols = _numeric_columns(df)
    if len(numeric_cols) < 2:
        return {
            "numeric_columns": numeric_cols,
            "matrix": {},
            "strong_positive": [],
            "strong_negative": [],
            "weak_relationships": [],
            "note": "Correlation requires at least two numeric columns.",
        }
    corr = df[numeric_cols].astype(float).corr(method=method)
    matrix = {c: {c2: _clean_scalar(corr.loc[c, c2]) for c2 in numeric_cols} for c in numeric_cols}

    strong_pos, strong_neg, weak = [], [], []
    seen = set()
    for i, c1 in enumerate(numeric_cols):
        for c2 in numeric_cols[i + 1:]:
            key = tuple(sorted([c1, c2]))
            if key in seen:
                continue
            seen.add(key)
            val = corr.loc[c1, c2]
            if pd.isna(val):
                continue
            entry = {"column_a": c1, "column_b": c2, "correlation": _clean_scalar(val)}
            if val >= threshold:
                strong_pos.append(entry)
            elif val <= -threshold:
                strong_neg.append(entry)
            else:
                weak.append(entry)

    strong_pos.sort(key=lambda x: x["correlation"], reverse=True)
    strong_neg.sort(key=lambda x: x["correlation"])

    return {
        "numeric_columns": numeric_cols,
        "matrix": matrix,
        "threshold": threshold,
        "strong_positive": strong_pos,
        "strong_negative": strong_neg,
        "weak_relationships": weak,
        "disclaimer": "Correlation does not prove causation.",
    }


# ---------------------------------------------------------------------------
# Category analysis
# ---------------------------------------------------------------------------

def category_analysis(df: pd.DataFrame, column: str, top_n: int = 15) -> dict:
    _require_column(df, column)
    n = df.shape[0]
    vc = df[column].astype(str).value_counts()
    total = int(vc.sum())
    top = vc.head(top_n)
    rare = vc[vc / total < 0.01] if total else vc[0:0]
    return {
        "column": column,
        "unique_categories": int(vc.shape[0]),
        "top_categories": [
            {"value": k, "count": int(v), "pct": round((v / total) * 100, 2) if total else 0.0}
            for k, v in top.items()
        ],
        "rare_categories": [
            {"value": k, "count": int(v), "pct": round((v / total) * 100, 2) if total else 0.0}
            for k, v in rare.items()
        ][:top_n],
    }


# ---------------------------------------------------------------------------
# Grouped analysis
# ---------------------------------------------------------------------------

_AGG_MAP = {
    "count": "count", "sum": "sum", "mean": "mean", "average": "mean",
    "median": "median", "min": "min", "max": "max",
}


def grouped_analysis(df: pd.DataFrame, group_by: str, metric: str, aggregation: str = "sum") -> dict:
    _require_column(df, group_by)
    agg = _AGG_MAP.get(aggregation.lower())
    if agg is None:
        raise AnalysisError(f"Unsupported aggregation '{aggregation}'. Use one of {list(_AGG_MAP)}.")

    if agg != "count":
        _require_column(df, metric)
        if not pd.api.types.is_numeric_dtype(df[metric]):
            raise AnalysisError(f"Column '{metric}' is not numeric; cannot apply '{aggregation}'.")
        grouped = df.groupby(group_by)[metric].agg(agg)
    else:
        grouped = df.groupby(group_by).size()

    grouped = grouped.sort_values(ascending=False)
    rows = [{"group": _clean_scalar(k), "value": _clean_scalar(v)} for k, v in grouped.items()]
    return {
        "group_by": group_by,
        "metric": metric if agg != "count" else "row_count",
        "aggregation": aggregation,
        "groups": rows[:200],
        "group_count": int(grouped.shape[0]),
    }


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------

_FREQ_MAP = {"daily": "D", "weekly": "W", "monthly": "ME", "quarterly": "QE", "yearly": "YE",
             "d": "D", "w": "W", "m": "ME", "q": "QE", "y": "YE"}


def timeseries_analysis(df: pd.DataFrame, date_column: str, value_column: str,
                         frequency: str = "M", aggregation: str = "sum") -> dict:
    _require_column(df, date_column)
    _require_column(df, value_column)
    agg = _AGG_MAP.get(aggregation.lower())
    if agg is None:
        raise AnalysisError(f"Unsupported aggregation '{aggregation}'.")

    freq = _FREQ_MAP.get(frequency.lower(), frequency.upper())

    work = df[[date_column, value_column]].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce", format="mixed")
    work = work.dropna(subset=[date_column])
    if work.empty:
        raise AnalysisError(f"Column '{date_column}' could not be parsed as dates.")

    if agg != "count":
        if not pd.api.types.is_numeric_dtype(work[value_column]):
            raise AnalysisError(f"Column '{value_column}' is not numeric; cannot apply '{aggregation}'.")
        series = work.set_index(date_column)[value_column].resample(freq).agg(agg)
    else:
        series = work.set_index(date_column)[value_column].resample(freq).count()

    series = series.fillna(0)
    points = [{"period": idx.isoformat(), "value": _clean_scalar(val)} for idx, val in series.items()]

    values = [p["value"] for p in points if p["value"] is not None]
    peak = max(points, key=lambda p: p["value"]) if values else None
    trough = min(points, key=lambda p: p["value"]) if values else None
    change_pct = None
    if len(values) >= 2 and values[0] not in (0, None):
        change_pct = round(((values[-1] - values[0]) / abs(values[0])) * 100, 2)

    return {
        "date_column": date_column,
        "value_column": value_column,
        "frequency": frequency,
        "aggregation": aggregation,
        "points": points,
        "peak_period": peak,
        "trough_period": trough,
        "overall_change_pct": change_pct,
        "note": "Trend direction is derived from calculated period totals only; no forecasting model is applied.",
    }


# ---------------------------------------------------------------------------
# KPI builder
# ---------------------------------------------------------------------------

def kpi_analysis(df: pd.DataFrame, metric_column: str, aggregation: str = "sum",
                  group_by: str | None = None, target: float | None = None) -> dict:
    _require_column(df, metric_column)
    agg = _AGG_MAP.get(aggregation.lower())
    if agg is None:
        raise AnalysisError(f"Unsupported aggregation '{aggregation}'.")

    if agg != "count" and not pd.api.types.is_numeric_dtype(df[metric_column]):
        raise AnalysisError(f"Column '{metric_column}' is not numeric; cannot apply '{aggregation}'.")

    if group_by:
        _require_column(df, group_by)
        grouped = df.groupby(group_by)[metric_column].agg(agg) if agg != "count" else df.groupby(group_by).size()
        breakdown = [{"group": _clean_scalar(k), "value": _clean_scalar(v)} for k, v in grouped.sort_values(ascending=False).items()]
        current_value = _clean_scalar(grouped.sum() if agg in ("sum", "count") else grouped.mean())
    else:
        breakdown = None
        if agg == "count":
            current_value = int(df[metric_column].count())
        else:
            current_value = _clean_scalar(getattr(df[metric_column].astype(float), agg)())

    result = {
        "metric_column": metric_column,
        "aggregation": aggregation,
        "current_value": current_value,
        "target": target,
        "breakdown": breakdown,
    }
    if target is not None and current_value is not None:
        result["difference"] = _clean_scalar(current_value - target)
        result["pct_to_target"] = round((current_value / target) * 100, 2) if target else None
    return result
