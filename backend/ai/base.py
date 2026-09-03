"""
DataForge AI - AI provider abstraction.

    AIProvider
      +-- OpenAIProvider
      +-- AnthropicProvider
      +-- GeminiProvider

The rest of the application talks only to this interface, never to a
specific provider's SDK/API directly - this is what makes automatic
fallback between providers possible.
"""
from __future__ import annotations
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from backend.ai.prompts import (
    build_prompt, INSIGHTS_SCHEMA, BUSINESS_INSIGHTS_SCHEMA,
    CHART_EXPLANATION_SCHEMA, DATA_QUESTION_SCHEMA, CLEANING_SUGGESTIONS_SCHEMA,
)
from backend.schemas import (
    AIInsightsResult, BusinessInsightsResult, ChartExplanationResult,
    DataQuestionResult, CleaningSuggestionsResult,
)


class AIError(Exception):
    """Raised for any AI provider failure. `category` drives fallback + logging."""
    CATEGORIES = {
        "missing_key", "invalid_key", "quota_exceeded", "rate_limited",
        "timeout", "network_error", "malformed_response", "provider_error", "unknown",
    }

    def __init__(self, message: str, category: str = "unknown"):
        super().__init__(message)
        self.category = category if category in self.CATEGORIES else "unknown"


def _extract_json(text: str) -> dict:
    """Extract a JSON object from a model response, tolerating markdown fences / stray text."""
    text = text.strip()
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        # Fall back to the first {...} block in the text
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError(f"Model returned malformed JSON: {e}", category="malformed_response")


class AIProvider(ABC):
    name: str = "base"

    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ---- Provider-specific transport (implemented by subclasses) ----
    @abstractmethod
    async def _call_raw(self, system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str:
        """Send a single-turn request and return the raw text response. Raises AIError on failure."""
        raise NotImplementedError

    async def test_connection(self) -> dict:
        if not self.is_configured():
            raise AIError(f"{self.name}: API key not configured.", category="missing_key")
        start = time.perf_counter()
        text = await self._call_raw(
            "You are a connectivity test endpoint. Reply with only the word OK.",
            "Reply with only the word OK.",
            max_tokens=5,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        return {"latency_ms": latency_ms, "raw_response": text[:100]}

    async def _structured_call(self, instruction: str, schema_example: dict,
                                verified_statistics: dict, extra_context: str = "",
                                max_tokens: int = 900) -> dict:
        if not self.is_configured():
            raise AIError(f"{self.name}: API key not configured.", category="missing_key")
        system_prompt, user_prompt = build_prompt(instruction, schema_example, verified_statistics, extra_context)
        raw = await self._call_raw(system_prompt, user_prompt, max_tokens=max_tokens)
        return _extract_json(raw)

    # ---- High-level structured operations (shared across all providers) ----

    async def interpret_analysis(self, verified_statistics: dict, focus: str | None = None) -> AIInsightsResult:
        instruction = (
            "Analyse the following verified dataset statistics and produce an AI Data Analyst "
            "report: an executive summary, key findings, trends, anomalies, potential business "
            "implications, questions worth investigating, recommended next analysis, and limitations."
        )
        if focus:
            instruction += f" Pay particular attention to: {focus}."
        data = await self._structured_call(instruction, INSIGHTS_SCHEMA, verified_statistics, max_tokens=1200)
        return AIInsightsResult(**data)

    async def generate_business_insights(self, verified_statistics: dict) -> BusinessInsightsResult:
        instruction = (
            "Based on the verified dataset profile, KPIs, correlations, and trends provided, "
            "generate business insights: top 5 insights, potential opportunities, potential risks, "
            "suggested next steps, and data limitations. Do not claim causal relationships without evidence."
        )
        data = await self._structured_call(instruction, BUSINESS_INSIGHTS_SCHEMA, verified_statistics, max_tokens=1000)
        return BusinessInsightsResult(**data)

    async def explain_chart(self, chart_context: dict) -> ChartExplanationResult:
        instruction = (
            "The following is chart metadata and the ACTUAL aggregated data values used to render "
            "a chart in a dashboard. Explain the chart: main pattern, largest values, smallest values, "
            "trend, potential interpretation, and limitations."
        )
        data = await self._structured_call(instruction, CHART_EXPLANATION_SCHEMA, chart_context, max_tokens=700)
        return ChartExplanationResult(**data)

    async def answer_data_question(self, question: str, query_result: dict) -> DataQuestionResult:
        instruction = (
            f"The user asked this question about their dataset: \"{question}\"\n"
            "A deterministic Python calculation (shown below in verified_statistics) already produced "
            "the exact numeric answer. Explain that result in clear natural language. Do NOT change the "
            "number or compute a different answer - only explain the one provided."
        )
        data = await self._structured_call(instruction, DATA_QUESTION_SCHEMA, query_result, max_tokens=500)
        return DataQuestionResult(**data)

    async def generate_report(self, verified_statistics: dict, report_type: str) -> AIInsightsResult:
        instruction = (
            f"Generate content for a '{report_type}' report based on the verified statistics below. "
            "Provide an executive summary, key findings, trends, anomalies, business implications, "
            "questions worth investigating, recommended next analysis, and limitations."
        )
        data = await self._structured_call(instruction, INSIGHTS_SCHEMA, verified_statistics, max_tokens=1200)
        return AIInsightsResult(**data)

    async def suggest_cleaning_steps(self, profile: dict) -> CleaningSuggestionsResult:
        instruction = (
            "Based on this verified dataset profile (missing values, types, duplicates), suggest data "
            "cleaning steps. For each suggestion give the column, the issue, the suggested operation "
            "(one of: remove_duplicates, drop_missing, fill_missing_numeric, fill_missing_categorical, "
            "trim_whitespace, standardize_case, convert_dtype, parse_dates), and a short rationale."
        )
        data = await self._structured_call(instruction, CLEANING_SUGGESTIONS_SCHEMA, profile, max_tokens=900)
        return CleaningSuggestionsResult(**data)
