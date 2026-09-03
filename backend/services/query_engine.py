"""
DataForge AI - Safe Query Engine ("Ask Your Data").

CRITICAL DESIGN RULE: this module NEVER executes AI-generated code and
NEVER calls eval()/exec(). A natural-language question is matched, using
plain keyword/column-name matching, to one of a small set of PRE-DEFINED
analytical operations (sum, mean, median, count, min, max, group-by,
correlation). The resulting number is calculated by pandas. Only the
final structured result is ever handed to an AI model - and only to be
explained in words, never to be recomputed or second-guessed.
"""
from __future__ import annotations
import re
import difflib
import pandas as pd

from backend.services.profiling import _clean_scalar

AGG_KEYWORDS = [
    (r"\baverage\b|\bmean\b|\bavg\b", "mean"),
    (r"\btotal\b|\bsum\b", "sum"),
    (r"\bmedian\b", "median"),
    (r"\bhow many\b|\bcount\b|\bnumber of\b", "count"),
    (r"\bhighest\b|\bmax(imum)?\b|\blargest\b|\btop\b|\bbest\b|\bgreatest\b", "max"),
    (r"\blowest\b|\bmin(imum)?\b|\bsmallest\b|\bworst\b", "min"),
    (r"\bstandard deviation\b|\bstd\b|\bvariance\b|\bspread\b", "std"),
    (r"\bunique\b|\bdistinct\b", "nunique"),
    (r"\bcorrelat", "correlation"),
]

GROUP_PATTERN = re.compile(
    r"\b(?:by|per|for each|in each|within each|across|each)\s+([a-zA-Z0-9_ ]+?)(?:$|\?|\.|,|\bfor\b)",
    re.IGNORECASE,
)
WHICH_PATTERN = re.compile(r"\bwhich\s+([a-zA-Z0-9_ ]+?)\s+(?:has|have|had|is|are|was|were|got)\b", re.IGNORECASE)


def _find_columns(question: str, columns: list[str]) -> list[str]:
    """Find dataset columns referenced in the question (case-insensitive, fuzzy)."""
    q_lower = question.lower()
    found = []
    # exact / substring match first (longest column names first to avoid partial shadowing)
    for col in sorted(columns, key=len, reverse=True):
        col_norm = col.lower().replace("_", " ")
        if col_norm in q_lower or col.lower() in q_lower:
            found.append(col)
    if found:
        return found
    # fuzzy match against individual words/phrases as a fallback
    words = re.findall(r"[a-zA-Z0-9_]+", q_lower)
    candidates = []
    for col in columns:
        col_norm = col.lower().replace("_", " ")
        best = difflib.get_close_matches(col_norm, [" ".join(words[i:i+len(col_norm.split())])
                                                      for i in range(len(words))], n=1, cutoff=0.72)
        if best:
            candidates.append(col)
    return candidates


def detect_aggregation(question: str) -> str | None:
    q = question.lower()
    for pattern, agg in AGG_KEYWORDS:
        if re.search(pattern, q):
            return agg
    return None


def detect_group_column(question: str, columns: list[str]) -> str | None:
    for pattern in (GROUP_PATTERN, WHICH_PATTERN):
        match = pattern.search(question)
        if match:
            phrase = match.group(1).strip()
            candidates = _find_columns(phrase, columns)
            if candidates:
                return candidates[0]
    return None


class QueryEngineError(ValueError):
    pass


def answer_question(df: pd.DataFrame, question: str) -> dict:
    """
    Parse a natural-language question into a predefined analytical
    operation and execute it deterministically with pandas.
    Returns a structured result describing exactly what was calculated.
    """
    if not question or not question.strip():
        raise QueryEngineError("Please enter a question.")

    columns = list(df.columns)
    numeric_columns = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])]

    aggregation = detect_aggregation(question)
    group_col = detect_group_column(question, columns)
    mentioned_cols = _find_columns(question, columns)

    # Fallback: "which <category>" without an explicit trigger word (e.g. "top region by
    # revenue") - if a non-numeric column is mentioned alongside a numeric one and no group
    # column was found yet, treat the categorical column as the implied group-by dimension.
    if group_col is None:
        categorical_mentioned = [c for c in mentioned_cols if c not in numeric_columns]
        numeric_candidates_pre = [c for c in mentioned_cols if c in numeric_columns]
        if categorical_mentioned and numeric_candidates_pre and aggregation in ("max", "min", "sum", "mean", "median"):
            group_col = categorical_mentioned[0]

    # remove group column from mentioned metric candidates
    metric_candidates = [c for c in mentioned_cols if c != group_col]
    numeric_mentioned = [c for c in metric_candidates if c in numeric_columns]

    if aggregation is None:
        aggregation = "mean" if numeric_mentioned else "count"

    # Case: correlation between two numeric columns
    if aggregation == "correlation":
        if len(numeric_mentioned) < 2:
            raise QueryEngineError(
                "I could not identify two numeric columns to correlate. "
                "Please mention both column names explicitly."
            )
        c1, c2 = numeric_mentioned[0], numeric_mentioned[1]
        value = df[[c1, c2]].dropna().astype(float).corr().loc[c1, c2]
        return {
            "operation": "correlation",
            "columns": [c1, c2],
            "result": _clean_scalar(value),
            "explanation_basis": f"Pearson correlation between '{c1}' and '{c2}' computed with pandas.corr().",
        }

    # Case: grouped question ("which region has the highest revenue")
    if group_col and (numeric_mentioned or aggregation == "count"):
        metric = numeric_mentioned[0] if numeric_mentioned else None
        if aggregation in ("max", "min") and metric:
            grouped = df.groupby(group_col)[metric].sum()
            extreme = grouped.idxmax() if aggregation == "max" else grouped.idxmin()
            return {
                "operation": f"group_{aggregation}",
                "group_by": group_col,
                "metric": metric,
                "result_group": _clean_scalar(extreme),
                "result_value": _clean_scalar(grouped.loc[extreme]),
                "full_breakdown": [{"group": _clean_scalar(k), "value": _clean_scalar(v)}
                                    for k, v in grouped.sort_values(ascending=False).items()][:20],
                "explanation_basis": f"Grouped '{metric}' by '{group_col}' using sum(), then took the {aggregation}.",
            }
        if aggregation == "count":
            grouped = df.groupby(group_col).size().sort_values(ascending=False)
            return {
                "operation": "group_count",
                "group_by": group_col,
                "full_breakdown": [{"group": _clean_scalar(k), "value": int(v)} for k, v in grouped.items()][:20],
                "explanation_basis": f"Counted rows per '{group_col}' using groupby().size().",
            }
        if metric:
            grouped = df.groupby(group_col)[metric].agg(aggregation if aggregation != "std" else "std")
            return {
                "operation": f"group_{aggregation}",
                "group_by": group_col,
                "metric": metric,
                "full_breakdown": [{"group": _clean_scalar(k), "value": _clean_scalar(v)}
                                    for k, v in grouped.sort_values(ascending=False).items()][:20],
                "explanation_basis": f"Grouped '{metric}' by '{group_col}' using {aggregation}().",
            }

    # Case: simple aggregate over one numeric column
    if numeric_mentioned:
        col = numeric_mentioned[0]
        s = df[col].dropna().astype(float)
        if aggregation == "nunique":
            value = df[col].nunique()
        elif aggregation in ("mean", "sum", "median", "min", "max", "std"):
            value = getattr(s, aggregation)()
        else:
            value = s.mean()
        return {
            "operation": aggregation,
            "column": col,
            "result": _clean_scalar(value),
            "row_count_considered": int(s.shape[0]),
            "explanation_basis": f"Calculated {aggregation}() of column '{col}' with pandas (missing values excluded).",
        }

    # Case: count of rows, optionally for a categorical column mentioned
    if metric_candidates:
        col = metric_candidates[0]
        if aggregation == "nunique" or "unique" in question.lower() or "how many" in question.lower():
            value = int(df[col].nunique())
            return {
                "operation": "nunique",
                "column": col,
                "result": value,
                "explanation_basis": f"Counted unique values in column '{col}' with pandas.nunique().",
            }
        vc = df[col].astype(str).value_counts().head(10)
        return {
            "operation": "value_counts",
            "column": col,
            "full_breakdown": [{"group": k, "value": int(v)} for k, v in vc.items()],
            "explanation_basis": f"Counted occurrences of each value in column '{col}' with pandas.value_counts().",
        }

    # Fallback: total row count
    return {
        "operation": "row_count",
        "result": int(df.shape[0]),
        "explanation_basis": (
            "Could not confidently match a specific column in your question, "
            "so the total row count of the dataset is returned. Try mentioning "
            "an exact column name for a more specific answer."
        ),
        "available_columns": columns,
    }
