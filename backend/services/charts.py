"""
DataForge AI - Chart data generation.
Computes real aggregated data from the dataset and returns a
Chart.js-ready structure. No fake or placeholder data is ever produced.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from backend.services.analysis import AnalysisError, _AGG_MAP
from backend.services.profiling import _clean_scalar

VALID_CHART_TYPES = {"bar", "line", "pie", "scatter", "histogram", "box"}


def build_chart(df: pd.DataFrame, chart_type: str, x: str | None, y: str | None,
                 aggregation: str = "count", group_by: str | None = None, bins: int = 10) -> dict:
    if chart_type not in VALID_CHART_TYPES:
        raise AnalysisError(f"Unsupported chart type '{chart_type}'. Choose from {sorted(VALID_CHART_TYPES)}.")

    if chart_type == "histogram":
        return _histogram(df, x or y, bins)
    if chart_type == "box":
        return _box(df, x or y)
    if chart_type == "scatter":
        return _scatter(df, x, y)
    if chart_type == "pie":
        return _categorical_agg(df, x, y, aggregation, chart_type="pie")
    # bar / line share the same aggregation logic
    return _categorical_agg(df, x, y, aggregation, chart_type=chart_type, group_by=group_by)


def _histogram(df: pd.DataFrame, column: str | None, bins: int) -> dict:
    if not column or column not in df.columns:
        raise AnalysisError("A valid numeric column is required for a histogram.")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise AnalysisError(f"Column '{column}' is not numeric.")
    series = df[column].dropna().astype(float)
    counts, edges = np.histogram(series, bins=max(2, min(bins, 50)))
    labels = [f"{edges[i]:.2f} - {edges[i+1]:.2f}" for i in range(len(edges) - 1)]
    return {
        "chart_type": "histogram",
        "labels": labels,
        "datasets": [{"label": column, "data": [int(c) for c in counts]}],
        "x_label": column,
        "y_label": "Frequency",
    }


def _box(df: pd.DataFrame, column: str | None) -> dict:
    if not column or column not in df.columns:
        raise AnalysisError("A valid numeric column is required for a box plot.")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise AnalysisError(f"Column '{column}' is not numeric.")
    s = df[column].dropna().astype(float)
    q1, med, q3 = s.quantile(0.25), s.median(), s.quantile(0.75)
    iqr = q3 - q1
    lower = s[s >= q1 - 1.5 * iqr].min()
    upper = s[s <= q3 + 1.5 * iqr].max()
    outliers = s[(s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)].tolist()
    return {
        "chart_type": "box",
        "labels": [column],
        "datasets": [{
            "label": column,
            "data": [{
                "min": _clean_scalar(lower), "q1": _clean_scalar(q1), "median": _clean_scalar(med),
                "q3": _clean_scalar(q3), "max": _clean_scalar(upper),
            }],
        }],
        "outliers": [_clean_scalar(v) for v in outliers[:25]],
        "x_label": column,
        "y_label": "Value",
    }


def _scatter(df: pd.DataFrame, x: str | None, y: str | None) -> dict:
    if not x or not y or x not in df.columns or y not in df.columns:
        raise AnalysisError("Both x and y numeric columns are required for a scatter chart.")
    if not pd.api.types.is_numeric_dtype(df[x]) or not pd.api.types.is_numeric_dtype(df[y]):
        raise AnalysisError("Scatter chart requires numeric x and y columns.")
    sample = df[[x, y]].dropna()
    if len(sample) > 2000:
        sample = sample.sample(2000, random_state=42)
    points = [{"x": _clean_scalar(r[x]), "y": _clean_scalar(r[y])} for _, r in sample.iterrows()]
    return {
        "chart_type": "scatter",
        "labels": [],
        "datasets": [{"label": f"{x} vs {y}", "data": points}],
        "x_label": x,
        "y_label": y,
    }


def _categorical_agg(df: pd.DataFrame, x: str | None, y: str | None, aggregation: str,
                      chart_type: str, group_by: str | None = None, top_n: int = 25) -> dict:
    if not x or x not in df.columns:
        raise AnalysisError("A valid x-axis column is required.")
    agg = _AGG_MAP.get(aggregation.lower())
    if agg is None:
        raise AnalysisError(f"Unsupported aggregation '{aggregation}'.")

    if group_by and group_by in df.columns:
        if agg == "count":
            pivot = df.groupby([x, group_by]).size().unstack(fill_value=0)
        else:
            if not y or y not in df.columns or not pd.api.types.is_numeric_dtype(df[y]):
                raise AnalysisError("A valid numeric y-axis column is required for this aggregation.")
            pivot = df.groupby([x, group_by])[y].agg(agg).unstack(fill_value=0)
        pivot = pivot.head(top_n)
        labels = [str(v) for v in pivot.index.tolist()]
        datasets = [{"label": str(col), "data": [_clean_scalar(v) for v in pivot[col].tolist()]} for col in pivot.columns]
        return {"chart_type": chart_type, "labels": labels, "datasets": datasets, "x_label": x, "y_label": y or "Count"}

    if agg == "count":
        series = df[x].astype(str).value_counts().head(top_n)
    else:
        if not y or y not in df.columns or not pd.api.types.is_numeric_dtype(df[y]):
            raise AnalysisError("A valid numeric y-axis column is required for this aggregation.")
        series = df.groupby(x)[y].agg(agg).sort_values(ascending=False).head(top_n)

    labels = [str(v) for v in series.index.tolist()]
    data = [_clean_scalar(v) for v in series.tolist()]
    return {
        "chart_type": chart_type,
        "labels": labels,
        "datasets": [{"label": y if (y and agg != "count") else "Count", "data": data}],
        "x_label": x,
        "y_label": y if (y and agg != "count") else "Count",
    }
