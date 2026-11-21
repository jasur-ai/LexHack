"""Async LLM & embedding client supporting Gemini (AI Studio & Vertex AI Express AQ.*), OpenAI, OpenRouter, and Ollama."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import math
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from openai import (
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
)
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from lex_agent.config import Settings, get_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {
    "",
    "your-api-key-here",
    "your_api_key_here",
    "your-gemini-api-key-here",
    "sk-your-key-here",
    "changeme",
    "none",
    "null",
}

_GEMINI_NATIVE_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_VERTEX_EXPRESS_BASE = "https://aiplatform.googleapis.com/v1beta1/publishers/google/models"


def _extract_json_block(text: str) -> Any:
    """Robustly extract a JSON object or array from an LLM response."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_obj = cleaned.find("{")
        start_arr = cleaned.find("[")
        candidates = [i for i in (start_obj, start_arr) if i != -1]
        if not candidates:
            raise
        start = min(candidates)
        end = max(cleaned.rfind("}"), cleaned.rfind("]")) + 1
        return json.loads(cleaned[start:end])


class LLMClient:
    """Async chat completion client with native Vertex AI Express (AQ.*), Gemini AI Studio, and OpenAI-compat support."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: AsyncOpenAI | None = None
        self._http: httpx.AsyncClient | None = None

    def _resolved_api_key(self) -> str:
        key = (self.settings.llm_api_key or "").strip()
        if (key.lower() in _PLACEHOLDER_KEYS or key.lower().startswith("your-")) and self.settings.llm_provider == "gemini":
            key = (self.settings.gemini_api_key or "").strip()
        return key

    def _resolved_base_url(self) -> str:
        url = (self.settings.llm_base_url or "").strip()
        if self.settings.llm_provider == "gemini" and (not url or "api.openai.com" in url):
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return url or "https://api.openai.com/v1"

    @property
    def is_gemini_native(self) -> bool:
        """Use native Gemini REST API (`x-goog-api-key`) for Gemini provider & `AQ.` auth keys."""
        key = self._resolved_api_key()
        return self.settings.llm_provider == "gemini" or key.startswith("AQ.")

    def _gemini_models_base(self) -> str:
        url = (self.settings.llm_base_url or "").strip()
        if "aiplatform.googleapis.com" in url:
            return _VERTEX_EXPRESS_BASE
        return _GEMINI_NATIVE_BASE

    @property
    def is_mock(self) -> bool:
        key = self._resolved_api_key().lower()
        return self.settings.llm_provider == "mock" or key in _PLACEHOLDER_KEYS or key.startswith("your-")

    @property
    def active_mode_label(self) -> str:
        if self.is_mock:
            return "retrieval-only"
        return f"{self.settings.llm_provider}:{self.settings.llm_model}"

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._resolved_api_key() or "not-set",
                base_url=self._resolved_base_url(),
                timeout=90.0,
            )
        return self._client

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=15.0, read=180.0, write=30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=180.0),
            )
        return self._http

    async def warmup(self) -> None:
        """Pre-initialize persistent HTTP connection pool so the first user query connects immediately."""
        self._get_http()

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def _thinking_config(self, model: str) -> dict[str, Any] | None:
        """Lowest-latency reasoning setting supported by the model (Gemini 3+ rejects `minimal` on non-lite models)."""
        level = (self.settings.llm_thinking_level or "auto").strip().lower()
        low = (model or "").lower()
        if re.search(r"gemini-(?:[3-9]|\d{2})", low):
            if level == "auto":
                level = "minimal" if "lite" in low else "low"
            if level in {"minimal", "low", "medium", "high"}:
                return {"thinkingLevel": level}
            return None
        if "gemini-2.5" in low and "pro" not in low:
            return {"thinkingBudget": 0}
        return None

    @staticmethod
    def _messages_to_vertex_payload(
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
        thinking: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system_parts: list[dict[str, str]] = []
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = str(msg.get("content", "") or "")
            if not content:
                continue
            if role == "system":
                system_parts.append({"text": content})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        gen_cfg: dict[str, Any] = {"maxOutputTokens": max_tokens}
        # Gemini 3+ deprecates sampling parameters; older models still honour temperature.
        if not re.search(r"gemini-(?:[3-9]|\d{2})", (model or "").lower()):
            gen_cfg["temperature"] = temperature
        if thinking:
            gen_cfg["thinkingConfig"] = thinking
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": gen_cfg,
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        return payload

    def _gemini_attempts(self, model: str) -> list[tuple[str, dict[str, Any] | None]]:
        attempts: list[tuple[str, dict[str, Any] | None]] = [(model, self._thinking_config(model))]
        fallback = (self.settings.llm_fallback_model or "").strip()
        if fallback and fallback != model:
            attempts.append((fallback, self._thinking_config(fallback)))
        return attempts

    @staticmethod
    def _raise_for_gemini(status: int, body: str) -> None:
        if status in (401, 403):
            raise PermissionError(f"API authentication failed ({status}): {body[:400]}")
        raise RuntimeError(f"AI service error ({status}): {body[:400]}")

    async def _gemini_generate(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        http = self._get_http()
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._resolved_api_key()}
        last_status, last_body = 0, ""
        for attempt_model, thinking in self._gemini_attempts(model):
            for thinking_cfg in (thinking, None) if thinking else (None,):
                payload = self._messages_to_vertex_payload(
                    messages,
                    model=attempt_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    thinking=thinking_cfg,
                )
                resp = await http.post(
                    f"{self._gemini_models_base()}/{attempt_model}:generateContent",
                    headers=headers,
                    json=payload,
                    timeout=self.settings.llm_request_timeout,
                )
                if resp.status_code < 400:
                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if not candidates:
                        return ""
                    parts = candidates[0].get("content", {}).get("parts") or []
                    return "".join(
                        p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")
                    ).strip()
                last_status, last_body = resp.status_code, resp.text
                if resp.status_code == 400 and thinking_cfg and "think" in last_body.lower():
                    continue  # retry the same model without a thinking config
                break
            if last_status == 404:
                continue  # model not available for this key -> try the fallback model
            self._raise_for_gemini(last_status, last_body)
        self._raise_for_gemini(last_status, last_body)
        return ""

    async def _gemini_stream_generate(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        http = self._get_http()
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._resolved_api_key()}
        last_status, last_body = 0, ""
        for attempt_model, thinking in self._gemini_attempts(model):
            for thinking_cfg in (thinking, None) if thinking else (None,):
                payload = self._messages_to_vertex_payload(
                    messages,
                    model=attempt_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=False,
                    thinking=thinking_cfg,
                )
                url = f"{self._gemini_models_base()}/{attempt_model}:streamGenerateContent?alt=sse"
                async with http.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code >= 400:
                        last_status = resp.status_code
                        last_body = (await resp.aread()).decode("utf-8", errors="replace")
                    else:
                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            raw_data = line[5:].strip()
                            if not raw_data or raw_data == "[DONE]":
                                continue
                            try:
                                chunk = json.loads(raw_data)
                            except json.JSONDecodeError:
                                continue
                            for cand in chunk.get("candidates") or []:
                                for part in cand.get("content", {}).get("parts") or []:
                                    if isinstance(part, dict) and not part.get("thought"):
                                        txt = part.get("text")
                                        if txt:
                                            yield txt
                        return
                if last_status == 400 and thinking_cfg and "think" in last_body.lower():
                    continue
                break
            if last_status == 404:
                continue
            self._raise_for_gemini(last_status, last_body)
        self._raise_for_gemini(last_status, last_body)

    @retry(
        retry=retry_if_not_exception_type((AuthenticationError, PermissionDeniedError, BadRequestError, PermissionError, RuntimeError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        fast: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Generate a text completion."""
        if self.is_mock:
            return self._mock_complete(messages)

        model = self.settings.llm_fast_model if fast else self.settings.llm_model
        temp = self.settings.llm_temperature if temperature is None else temperature
        toks = max_tokens or self.settings.llm_max_tokens

        if self.is_gemini_native:
            return await self._gemini_generate(
                messages,
                model=model,
                temperature=temp,
                max_tokens=toks,
                json_mode=bool(response_format and response_format.get("type") == "json_object"),
            )

        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": toks,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = await client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()

    async def complete_json(
        self,
        messages: list[dict[str, Any]],
        *,
        fast: bool = False,
        temperature: float = 0.0,
        fallback: Any = None,
    ) -> Any:
        """Generate and parse a JSON object/array with graceful fallback."""
        if self.is_mock:
            return fallback if fallback is not None else {}

        try:
            raw = await self.complete(
                messages,
                fast=fast,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except (AuthenticationError, PermissionDeniedError, PermissionError):
            raise
        except Exception:
            raw = await self.complete(messages, fast=fast, temperature=temperature)

        try:
            return _extract_json_block(raw)
        except Exception as exc:
            logger.warning("Failed to parse JSON from LLM output: %s", exc)
            return fallback if fallback is not None else {}

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        fast: bool = False,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        """Execute a tool-calling turn returning content and any requested tool calls."""
        if self.is_mock or self.is_gemini_native:
            # Gemini native uses fast deterministic + cross-ref hops; skip redundant tool roundtrip
            return {"content": "", "tool_calls": []}

        client = self._get_client()
        model = self.settings.llm_fast_model if fast else self.settings.llm_model
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        msg = resp.choices[0].message
        parsed_calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            parsed_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": msg.content or "", "tool_calls": parsed_calls}

    async def stream_complete(
        self,
        messages: list[dict[str, Any]],
        *,
        fast: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream completion tokens live for SSE API responses."""
        if self.is_mock:
            yield self._mock_complete(messages)
            return

        model = self.settings.llm_fast_model if fast else self.settings.llm_model
        temp = self.settings.llm_temperature if temperature is None else temperature
        toks = max_tokens or self.settings.llm_max_tokens

        if self.is_gemini_native:
            async for delta in self._gemini_stream_generate(
                messages,
                model=model,
                temperature=temp,
                max_tokens=toks,
            ):
                yield delta
            return

        client = self._get_client()
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temp,
            max_tokens=toks,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    @staticmethod
    def _mock_complete(messages: list[dict[str, Any]]) -> str:
        user_msg = str(next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""))
        ev_idx = user_msg.find("RETRIEVED LEX.UZ EVIDENCE")
        if ev_idx != -1:
            excerpts = user_msg[ev_idx : ev_idx + 2400].strip()
            return (
                "[Retrieval-Only Mode — haqiqiy LLM_API_KEY hali agent/.env ga kiritilmagan]\n\n"
                "To'liq AI tahlil va javob sintezi uchun `agent/.env` faylida `LLM_API_KEY` (Gemini, OpenAI yoki Ollama) "
                "o'rnating va serverni qayta ishga tushiring.\n\n"
                "Hozircha Lex.uz bazasidan topilgan eng mos normalar:\n\n"
                f"{excerpts}"
            )
        return (
            "[Retrieval-Only Mode — `LLM_API_KEY` not configured in `agent/.env`]\n\n"
            "Set a valid `LLM_API_KEY` in `agent/.env` and restart the server.\n\n"
            f"Query summary: {user_msg[:300]}"
        )


class EmbeddingClient:
    """Multilingual embedding client supporting OpenAI API, local BGE-M3/E5, and fast hash fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._openai_client: AsyncOpenAI | None = None
        self._local_model: Any = None
        self._resolved_provider: str | None = None

    @property
    def dim(self) -> int:
        return self.settings.embedding_dim

    @property
    def is_hash_fallback(self) -> bool:
        provider = self._resolved_provider or self.settings.embedding_provider
        if provider == "hash":
            return True
        if provider == "local" and importlib.util.find_spec("sentence_transformers") is None:
            self._resolved_provider = "hash"
            return True
        return False

    def _ensure_local_model(self) -> Any:
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading local multilingual embedding model: %s", self.settings.embedding_model)
            self._local_model = SentenceTransformer(self.settings.embedding_model)
            model_dim = self._local_model.get_sentence_embedding_dimension()
            if model_dim:
                self.settings.embedding_dim = int(model_dim)
        return self._local_model

    def _get_openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.embedding_api_key or self.settings.llm_api_key,
                base_url=self.settings.embedding_base_url or self.settings.llm_base_url,
                timeout=60.0,
            )
        return self._openai_client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of multilingual legal texts into normalized float vectors."""
        if not texts:
            return []

        if self.is_hash_fallback:
            return [self._hash_embed(t, self.dim) for t in texts]

        provider = self._resolved_provider or self.settings.embedding_provider
        if provider == "openai":
            api_key = self.settings.embedding_api_key or self.settings.llm_api_key
            if not api_key or api_key.lower() in _PLACEHOLDER_KEYS:
                self._resolved_provider = "hash"
                return [self._hash_embed(t, self.dim) for t in texts]
            client = self._get_openai_client()
            resp = await client.embeddings.create(model=self.settings.embedding_model, input=texts)
            vectors = [item.embedding for item in resp.data]
            if vectors:
                self.settings.embedding_dim = len(vectors[0])
            return vectors

        if provider == "local":
            try:
                model = self._ensure_local_model()
                vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                return [v.tolist() for v in vecs]
            except Exception as exc:
                logger.warning("Local sentence-transformers unavailable (%s); using hash embeddings.", exc)
                self._resolved_provider = "hash"
                return [self._hash_embed(t, self.dim) for t in texts]

        return [self._hash_embed(t, self.dim) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        return vectors[0] if vectors else [0.0] * self.dim

    @staticmethod
    def _hash_embed(text: str, dim: int) -> list[float]:
        """Deterministic character + word n-gram projection for offline/CI execution."""
        vec = [0.0] * dim
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        if not normalized:
            return vec

        tokens = re.findall(r"[\w'-]+", normalized, flags=re.UNICODE)
        features: list[str] = list(tokens)
        for tok in tokens:
            if len(tok) >= 4:
                for i in range(len(tok) - 2):
                    features.append(f"c:{tok[i:i + 3]}")

        for feat in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            val = int.from_bytes(digest, "little")
            idx = val % dim
            sign = 1.0 if ((val >> 16) & 1) == 0 else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec
