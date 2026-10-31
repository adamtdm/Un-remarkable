"""Vision and OCR provider client supporting Google Gemini and OpenAI/Ollama."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class VisionProvider:
    """Dispatches vision and handwriting extraction prompts to cloud or local models."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: str = "",
        model: str = "gemini-2.0-flash",
        base_url: str = "",
    ) -> None:
        self.provider = provider.lower()
        self.api_key = api_key.strip()
        self.model = model.strip() or ("gemini-2.0-flash" if self.provider == "gemini" else "gpt-4o-mini")
        self.base_url = base_url.rstrip("/")

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str = "",
        timeout: float = 45.0,
    ) -> str:
        """Send image and prompt to configured model and return text response."""
        if self.provider == "gemini":
            return await self._call_gemini(image_bytes, prompt, system_prompt, timeout)
        else:
            return await self._call_openai_compatible(image_bytes, prompt, system_prompt, timeout)

    async def _call_gemini(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str,
        timeout: float,
    ) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is required")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {"key": self.api_key}

        b64_image = base64.b64encode(image_bytes).decode("ascii")

        contents: list[dict[str, Any]] = [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64_image,
                        }
                    },
                ]
            }
        ]

        payload = {"contents": contents}

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, params=params, json=payload)
            if resp.status_code != 200:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                except Exception:
                    pass
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {err_detail}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()

    async def _call_openai_compatible(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str,
        timeout: float,
    ) -> str:
        base = self.base_url or "https://api.openai.com"
        url = f"{base}/v1/chat/completions"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        b64_image = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64_image}"

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        })

        payload = {
            "model": self.model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Vision API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "").strip()

    async def test_connection(self) -> dict[str, Any]:
        """Test the provider configuration with a minimal ping prompt."""
        t0 = time.time()
        # 1x1 transparent PNG for health check
        blank_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        reply = await self.analyze_image(
            blank_png,
            prompt="Respond with only the single word: OK",
            timeout=15.0,
        )
        latency = round(time.time() - t0, 3)
        return {"ok": True, "provider": self.provider, "model": self.model, "latency_s": latency, "reply": reply}


def get_vision_provider(db: Any) -> VisionProvider | None:
    """Load vision provider from database app state."""
    settings_raw = db.get_state("vision_settings", "")
    if not settings_raw:
        return None
    try:
        conf = json.loads(settings_raw)
        if not conf.get("api_key") and conf.get("provider") != "ollama":
            return None
        return VisionProvider(
            provider=conf.get("provider", "gemini"),
            api_key=conf.get("api_key", ""),
            model=conf.get("model", ""),
            base_url=conf.get("base_url", ""),
        )
    except Exception as e:
        logger.warning("Failed to load vision settings: %s", e)
        return None
