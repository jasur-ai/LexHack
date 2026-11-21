"""Independent Auditor LLM client supporting Gemini (AQ./AIza native REST), OpenAI-compat, Ollama, and offline fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from evaluator_agent.config import AuditorSettings, get_settings

logger = logging.getLogger(__name__)

_GEMINI_NATIVE_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
        if not starts:
            raise
        start = min(starts)
        end = max(cleaned.rfind("}"), cleaned.rfind("]")) + 1
        return json.loads(cleaned[start:end])


class AuditorLLMClient:
    """Zero-trust independent LLM for adversarial trap generation, claim auditing, and benchmark critique."""

    def __init__(self, settings: AuditorSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._http: httpx.AsyncClient | None = None

    def _api_key(self) -> str:
        return self.settings.resolve_api_key()

    @property
    def is_available(self) -> bool:
        return self.settings.auditor_llm_provider != "mock" and bool(self._api_key())

    @property
    def is_gemini_native(self) -> bool:
        key = self._api_key()
        return self.settings.auditor_llm_provider == "gemini" or key.startswith("AQ.")

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.auditor_llm_timeout, connect=12.0),
                limits=httpx.Limits(max_connections=16, max_keepalive_connections=8, keepalive_expiry=180.0),
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    @staticmethod
    def _gemini_generation_config(model: str, temperature: float, max_tokens: int, json_mode: bool) -> dict[str, Any]:
        """Build a generationConfig that each Gemini family accepts.

        Gemini 3+/4 reject ``thinkingLevel: minimal`` on non-lite models and no longer take a temperature;
        Gemini 2.5 uses a token ``thinkingBudget`` instead.
        """
        low = model.lower()
        cfg: dict[str, Any] = {"maxOutputTokens": max_tokens}
        if re.search(r"gemini-(?:3|4)", low):
            cfg["thinkingConfig"] = {"thinkingLevel": "minimal" if "lite" in low else "low"}
        else:
            cfg["temperature"] = temperature
            if "gemini-2.5" in low:
                cfg["thinkingConfig"] = {"thinkingBudget": 0 if ("flash" in low and "pro" not in low) else 128}
        if json_mode:
            cfg["responseMimeType"] = "application/json"
        return cfg

    async def _gemini_native(
        self, system_prompt: str, user_prompt: str, *, json_mode: bool, temperature: float
    ) -> str:
        http = self._get_http()
        models = [self.settings.auditor_llm_model]
        fallback = (self.settings.auditor_llm_fallback_model or "").strip()
        if fallback and fallback not in models:
            models.append(fallback)
        last_error = ""
        for model in models:
            gen_cfg = self._gemini_generation_config(
                model, temperature, self.settings.auditor_llm_max_tokens, json_mode
            )
            for attempt in range(2):
                payload: dict[str, Any] = {
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": gen_cfg,
                }
                resp = await http.post(
                    f"{_GEMINI_NATIVE_BASE}/{model}:generateContent",
                    headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key()},
                    json=payload,
                )
                if resp.status_code < 400:
                    data = resp.json()
                    cands = data.get("candidates") or []
                    if not cands:
                        return ""
                    parts = cands[0].get("content", {}).get("parts") or []
                    return "".join(
                        p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")
                    ).strip()
                last_error = f"{resp.status_code}: {resp.text[:300]}"
                body_low = resp.text.lower()
                if resp.status_code == 400 and attempt == 0 and ("thinking" in body_low or "temperature" in body_low):
                    # Unknown model family rules: retry once with the most conservative config.
                    gen_cfg = {k: v for k, v in gen_cfg.items() if k not in {"thinkingConfig", "temperature"}}
                    continue
                break
            if not last_error.startswith("404"):
                break
            logger.warning("Auditor model %s unavailable (404); trying fallback model.", model)
        logger.warning("Auditor Gemini call failed (%s)", last_error)
        return ""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        if not self.is_available:
            return ""

        temp = self.settings.auditor_llm_temperature if temperature is None else temperature
        try:
            if self.is_gemini_native:
                return await self._gemini_native(system_prompt, user_prompt, json_mode=json_mode, temperature=temp)

            # OpenAI / OpenRouter / Ollama compatible endpoint
            base = self.settings.auditor_llm_base_url.rstrip("/")
            body: dict[str, Any] = {
                "model": self.settings.auditor_llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temp,
                "max_tokens": self.settings.auditor_llm_max_tokens,
            }
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            resp = await self._get_http().post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"},
                json=body,
            )
            if resp.status_code >= 400:
                logger.warning("Auditor OpenAI-compat call failed (%d): %s", resp.status_code, resp.text[:300])
                return ""
            data = resp.json()
            return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except httpx.HTTPError as exc:
            # Network trouble must degrade to deterministic-only auditing, never crash an audit run.
            logger.warning("Auditor LLM unreachable (%s: %s)", type(exc).__name__, exc)
            return ""

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        fallback: Any = None,
    ) -> Any:
        if not self.is_available:
            return fallback if fallback is not None else {}
        try:
            raw = await self.complete(system_prompt, user_prompt, json_mode=True, temperature=0.0)
            if not raw:
                return fallback if fallback is not None else {}
            return _extract_json(raw)
        except Exception as exc:
            logger.warning("Auditor JSON parsing failed: %s", exc)
            return fallback if fallback is not None else {}
