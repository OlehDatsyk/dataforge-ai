"""DataForge AI - Google Gemini provider (generateContent REST API via httpx, no SDK dependency)."""
import httpx

from backend.ai.base import AIProvider, AIError


class GeminiProvider(AIProvider):
    name = "gemini"

    async def _call_raw(self, system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as e:
            raise AIError(f"Gemini request timed out: {e}", category="timeout")
        except httpx.RequestError as e:
            raise AIError(f"Gemini network error: {e}", category="network_error")

        if resp.status_code in (401, 403):
            raise AIError("Gemini: invalid API key.", category="invalid_key")
        if resp.status_code == 429:
            raise AIError(f"Gemini rate limit / quota error: {resp.text[:200]}", category="rate_limited")
        if resp.status_code >= 500:
            raise AIError(f"Gemini server error ({resp.status_code}).", category="provider_error")
        if resp.status_code != 200:
            raise AIError(f"Gemini request failed ({resp.status_code}): {resp.text[:200]}", category="provider_error")

        try:
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                block_reason = data.get("promptFeedback", {}).get("blockReason")
                raise AIError(f"Gemini returned no candidates (blockReason={block_reason}).", category="provider_error")
            parts = candidates[0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            if not text:
                raise KeyError("no text content")
            return text
        except AIError:
            raise
        except (KeyError, IndexError, ValueError) as e:
            raise AIError(f"Gemini returned an unexpected response shape: {e}", category="malformed_response")
