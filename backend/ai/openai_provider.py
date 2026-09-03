"""DataForge AI - OpenAI provider (Chat Completions API via httpx, no SDK dependency)."""
import httpx

from backend.ai.base import AIProvider, AIError

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(AIProvider):
    name = "openai"

    async def _call_raw(self, system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(API_URL, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIError(f"OpenAI request timed out: {e}", category="timeout")
        except httpx.RequestError as e:
            raise AIError(f"OpenAI network error: {e}", category="network_error")

        if resp.status_code == 401:
            raise AIError("OpenAI: invalid API key.", category="invalid_key")
        if resp.status_code == 429:
            body = resp.text.lower()
            category = "quota_exceeded" if "quota" in body else "rate_limited"
            raise AIError(f"OpenAI rate limit / quota error: {resp.text[:200]}", category=category)
        if resp.status_code >= 500:
            raise AIError(f"OpenAI server error ({resp.status_code}).", category="provider_error")
        if resp.status_code != 200:
            raise AIError(f"OpenAI request failed ({resp.status_code}): {resp.text[:200]}", category="provider_error")

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise AIError(f"OpenAI returned an unexpected response shape: {e}", category="malformed_response")
