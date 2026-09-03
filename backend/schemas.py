"""
DataForge AI - Pydantic schemas.
Used both for API request/response validation and for constraining
structured AI output (so AI responses have a predictable shape).
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AI structured output contracts
# ---------------------------------------------------------------------------

class KeyFinding(BaseModel):
    finding: str = ""
    evidence: str = ""
    importance: str = "medium"  # low / medium / high


class AIInsightsResult(BaseModel):
    executive_summary: str = ""
    key_findings: list[KeyFinding] = Field(default_factory=list)
    trends: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    business_implications: list[str] = Field(default_factory=list)
    questions_worth_investigating: list[str] = Field(default_factory=list)
    recommended_next_analysis: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class BusinessInsightsResult(BaseModel):
    top_insights: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class ChartExplanationResult(BaseModel):
    main_pattern: str = ""
    largest_values: str = ""
    smallest_values: str = ""
    trend: str = ""
    interpretation: str = ""
    limitations: str = ""


class DataQuestionResult(BaseModel):
    answer_explanation: str = ""
    caveats: list[str] = Field(default_factory=list)


class CleaningSuggestion(BaseModel):
    column: str = ""
    issue: str = ""
    suggestion: str = ""
    rationale: str = ""


class CleaningSuggestionsResult(BaseModel):
    suggestions: list[CleaningSuggestion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AI envelope (returned to frontend for every AI-backed endpoint)
# ---------------------------------------------------------------------------

class AIEnvelope(BaseModel):
    model_config = {"protected_namespaces": ()}

    success: bool
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    fallback_used: bool = False
    processing_time_ms: float = 0.0
    data: Optional[dict[str, Any]] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CleanOperationRequest(BaseModel):
    operation: str
    column: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class GroupAnalysisRequest(BaseModel):
    group_by: str
    metric: str
    aggregation: str = "sum"  # count/sum/mean/median/min/max


class CorrelationRequest(BaseModel):
    threshold: float = 0.5
    method: str = "pearson"


class OutlierRequest(BaseModel):
    method: str = "iqr"  # iqr / zscore
    threshold: float = 1.5
    columns: Optional[list[str]] = None


class TimeSeriesRequest(BaseModel):
    date_column: str
    value_column: str
    frequency: str = "M"  # D/W/M/Q/Y
    aggregation: str = "sum"


class KPIRequest(BaseModel):
    metric_column: str
    aggregation: str = "sum"
    group_by: Optional[str] = None
    target: Optional[float] = None


class ChartRequest(BaseModel):
    chart_type: str  # bar/line/pie/scatter/histogram/box
    x: Optional[str] = None
    y: Optional[str] = None
    aggregation: str = "count"
    group_by: Optional[str] = None
    bins: int = 10


class AskRequest(BaseModel):
    question: str
    provider: str = "auto"


class InsightsRequest(BaseModel):
    provider: str = "auto"
    focus: Optional[str] = None


class ExplainChartRequest(BaseModel):
    chart_type: str
    x: Optional[str] = None
    y: Optional[str] = None
    aggregation: str = "count"
    group_by: Optional[str] = None
    provider: str = "auto"
    chart_data: Optional[dict[str, Any]] = None


class ReportGenerateRequest(BaseModel):
    dataset_id: str
    report_type: str = "dataset_profile"  # dataset_profile/data_quality/business_analysis/kpi/trend/executive_summary
    provider: str = "auto"
    include_ai: bool = True
    export_format: str = "markdown"  # markdown/html/txt/json


class ProviderTestRequest(BaseModel):
    provider: str
