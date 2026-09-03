"""DataForge AI - Anthropic Claude provider (Messages API via httpx, no SDK dependency)."""
import httpx

from backend.ai.base import AIProvider, AIError

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    name = "anthropic"

    async def _call_raw(self, system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(API_URL, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIError(f"Anthropic request timed out: {e}", category="timeout")
        except httpx.RequestError as e:
            raise AIError(f"Anthropic network error: {e}", category="network_error")

        if resp.status_code == 401:
            raise AIError("Anthropic: invalid API key.", category="invalid_key")
        if resp.status_code == 429:
            raise AIError(f"Anthropic rate limit / quota error: {resp.text[:200]}", category="rate_limited")
        if resp.status_code >= 500:
            raise AIError(f"Anthropic server error ({resp.status_code}).", category="provider_error")
        if resp.status_code != 200:
            raise AIError(f"Anthropic request failed ({resp.status_code}): {resp.text[:200]}", category="provider_error")

        try:
            data = resp.json()
            parts = data.get("content", [])
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            if not text:
                raise KeyError("no text content")
            return text
        except (KeyError, IndexError, ValueError) as e:
            raise AIError(f"Anthropic returned an unexpected response shape: {e}", category="malformed_response")
