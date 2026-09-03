"""
DataForge AI - AI Provider Manager.

Handles:
  * Provider registry (OpenAI / Anthropic / Gemini)
  * Manual provider selection OR automatic fallback chain
  * Retrying malformed JSON once before moving to the next provider
  * Logging every attempt to the ai_logs table (never logs secrets)
  * Guaranteeing the app never crashes if every provider is unavailable
"""
from __future__ import annotations
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.ai.base import AIProvider, AIError
from backend.ai.openai_provider import OpenAIProvider
from backend.ai.anthropic_provider import AnthropicProvider
from backend.ai.gemini_provider import GeminiProvider
from backend.models import AILog


class AIManager:
    def __init__(self):
        self.providers: dict[str, AIProvider] = {
            "openai": OpenAIProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL, settings.AI_REQUEST_TIMEOUT_SECONDS),
            "anthropic": AnthropicProvider(settings.ANTHROPIC_API_KEY, settings.ANTHROPIC_MODEL, settings.AI_REQUEST_TIMEOUT_SECONDS),
            "gemini": GeminiProvider(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.AI_REQUEST_TIMEOUT_SECONDS),
        }

    def status(self) -> list[dict]:
        return [
            {
                "provider": name,
                "configured": p.is_configured(),
                "model": p.model,
            }
            for name, p in self.providers.items()
        ]

    def _fallback_order(self, requested: str) -> list[str]:
        requested = (requested or "auto").lower()
        if requested in self.providers:
            return [requested]
        # automatic: primary -> fallback -> secondary fallback, deduplicated, plus any
        # remaining configured providers not already covered.
        order = [settings.PRIMARY_AI_PROVIDER, settings.FALLBACK_AI_PROVIDER, settings.SECONDARY_FALLBACK_AI_PROVIDER]
        order = [p for p in order if p in self.providers]
        for name in self.providers:
            if name not in order:
                order.append(name)
        seen = set()
        deduped = []
        for p in order:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        return deduped

    def _log(self, db: Optional[Session], provider: str, model: Optional[str], operation: str,
              success: bool, fallback_used: bool, error_category: Optional[str], latency_ms: float):
        if db is None:
            return
        try:
            db.add(AILog(
                provider=provider, model=model, operation=operation, success=success,
                fallback_used=fallback_used, error_category=error_category, latency_ms=latency_ms,
            ))
            db.commit()
        except Exception:
            db.rollback()

    async def execute(self, operation: str, method_name: str, kwargs: dict,
                       requested_provider: str = "auto", db: Optional[Session] = None) -> dict:
        """
        Try providers in order until one succeeds. Returns an envelope dict:
        {success, provider_used, model_used, fallback_used, processing_time_ms, data, message}
        """
        order = self._fallback_order(requested_provider)
        attempts = 0
        overall_start = time.perf_counter()
        last_error_message = None

        for idx, provider_name in enumerate(order):
            provider = self.providers[provider_name]
            attempts += 1
            attempt_start = time.perf_counter()
            try:
                if not provider.is_configured():
                    raise AIError(f"{provider_name}: not configured (missing API key).", category="missing_key")

                method = getattr(provider, method_name)
                result = await method(**kwargs)

                # one retry on malformed JSON before giving up on this provider
                latency_ms = round((time.perf_counter() - attempt_start) * 1000, 1)
                self._log(db, provider_name, provider.model, operation, True, idx > 0, None, latency_ms)
                total_ms = round((time.perf_counter() - overall_start) * 1000, 1)
                return {
                    "success": True,
                    "provider_used": provider_name,
                    "model_used": provider.model,
                    "fallback_used": idx > 0,
                    "processing_time_ms": total_ms,
                    "data": result.model_dump() if hasattr(result, "model_dump") else result,
                    "message": None,
                }
            except AIError as e:
                latency_ms = round((time.perf_counter() - attempt_start) * 1000, 1)
                # one immediate retry for a malformed response only
                if e.category == "malformed_response":
                    try:
                        method = getattr(provider, method_name)
                        result = await method(**kwargs)
                        self._log(db, provider_name, provider.model, operation, True, idx > 0, None, latency_ms)
                        total_ms = round((time.perf_counter() - overall_start) * 1000, 1)
                        return {
                            "success": True, "provider_used": provider_name, "model_used": provider.model,
                            "fallback_used": idx > 0, "processing_time_ms": total_ms,
                            "data": result.model_dump() if hasattr(result, "model_dump") else result,
                            "message": None,
                        }
                    except AIError as e2:
                        e = e2
                self._log(db, provider_name, provider.model, operation, False, idx > 0, e.category, latency_ms)
                last_error_message = f"{provider_name}: {e}"
                continue
            except Exception as e:  # noqa: BLE001 - never let an unexpected error crash the request
                latency_ms = round((time.perf_counter() - attempt_start) * 1000, 1)
                self._log(db, provider_name, provider.model, operation, False, idx > 0, "unknown", latency_ms)
                last_error_message = f"{provider_name}: unexpected error - {e}"
                continue

        total_ms = round((time.perf_counter() - overall_start) * 1000, 1)
        return {
            "success": False,
            "provider_used": None,
            "model_used": None,
            "fallback_used": False,
            "processing_time_ms": total_ms,
            "data": None,
            "message": "All configured AI providers are currently unavailable."
                        + (f" Last error: {last_error_message}" if last_error_message else ""),
        }

    async def test_provider(self, provider_name: str, db: Optional[Session] = None) -> dict:
        provider = self.providers.get(provider_name)
        if provider is None:
            return {"provider": provider_name, "configured": False, "available": False, "error": "Unknown provider."}
        if not provider.is_configured():
            return {"provider": provider_name, "configured": False, "available": False, "latency_ms": None,
                     "error": "API key not configured."}
        start = time.perf_counter()
        try:
            result = await provider.test_connection()
            latency_ms = result["latency_ms"]
            self._log(db, provider_name, provider.model, "test_connection", True, False, None, latency_ms)
            return {"provider": provider_name, "configured": True, "available": True,
                     "latency_ms": latency_ms, "model": provider.model, "error": None}
        except AIError as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            self._log(db, provider_name, provider.model, "test_connection", False, False, e.category, latency_ms)
            return {"provider": provider_name, "configured": True, "available": False,
                     "latency_ms": latency_ms, "model": provider.model, "error": str(e), "error_category": e.category}


ai_manager = AIManager()
