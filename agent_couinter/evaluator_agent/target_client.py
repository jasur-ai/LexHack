"""Zero-trust HTTPX interrogation client for querying the Target Legal Agent (`agent/`)."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import httpx

from evaluator_agent.config import AuditorSettings, get_settings
from evaluator_agent.models import AuditLanguage, TargetAgentObservation

logger = logging.getLogger(__name__)


class TargetAgentClient:
    """Interrogates the primary Uzbekistan Legal Agent (`agent/`) over HTTP and captures raw responses."""

    def __init__(self, settings: AuditorSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.target_agent_url.rstrip("/")
        self.timeout = self.settings.target_agent_timeout
        self._http: httpx.AsyncClient | None = None

    def update_config(self, target_url: str, timeout: float | None = None) -> None:
        self.base_url = target_url.rstrip("/")
        if timeout is not None:
            self.timeout = timeout

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def check_health(self, *, override_url: str | None = None) -> dict[str, Any]:
        url = f"{(override_url or self.base_url).rstrip('/')}{self.settings.target_agent_health_path}"
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                data["reachable"] = True
                data["latency_ms"] = int((time.perf_counter() - t0) * 1000)
                data["target_url"] = (override_url or self.base_url).rstrip("/")
                return data
        except Exception as exc:
            return {
                "reachable": False,
                "target_url": (override_url or self.base_url).rstrip("/"),
                "error": str(exc),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }

    async def interrogate(
        self,
        question: str,
        *,
        language: AuditLanguage | None = None,
        as_of_date: date | None = None,
        override_url: str | None = None,
        override_timeout: float | None = None,
    ) -> TargetAgentObservation:
        """Send an adversarial legal probe to `agent/api/ask` and capture its unverified claims."""
        base = (override_url or self.base_url).rstrip("/")
        endpoint = f"{base}{self.settings.target_agent_ask_path}"
        timeout_val = override_timeout or self.timeout

        payload: dict[str, Any] = {
            "query": question,
            "enable_live_lex": True,
            "max_hops": 2,
            "answer_style": self.settings.target_agent_answer_style,
        }
        if language is not None:
            payload["response_language"] = language.value
        if as_of_date is not None:
            payload["as_of_date"] = as_of_date.isoformat()

        t0 = time.perf_counter()
        try:
            http = self._get_http()
            resp = await http.post(endpoint, json=payload, timeout=timeout_val)
            elapsed = int((time.perf_counter() - t0) * 1000)
            if resp.status_code >= 400:
                return TargetAgentObservation(
                    target_url=endpoint,
                    answer_text="",
                    latency_ms=elapsed,
                    error=f"HTTP {resp.status_code}: {resp.text[:350]}",
                )
            data = resp.json()
            ver = data.get("verification") or {}
            citations = list(data.get("citations") or [])
            # Agent >= 2.0 also returns the numbered sources behind the [n] markers; audit them too.
            known = {(str(c.get("doc_id")), str(c.get("article"))) for c in citations}
            for src in data.get("sources") or []:
                key = (str(src.get("doc_id")), str(src.get("article")))
                if key in known:
                    continue
                known.add(key)
                citations.append(
                    {
                        "doc_id": src.get("doc_id"),
                        "doc_title": src.get("full_title") or src.get("title"),
                        "article": src.get("article"),
                        "url": src.get("url"),
                        "status": src.get("status"),
                    }
                )
            return TargetAgentObservation(
                target_url=endpoint,
                answer_text=str(data.get("answer") or ""),
                reported_citations=citations,
                reported_confidence=ver.get("confidence_score"),
                reported_verified=ver.get("passed"),
                answer_mode=data.get("mode"),
                sources_count=len(data.get("sources") or []),
                latency_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("Target interrogation failed (%s): %s", endpoint, exc)
            return TargetAgentObservation(
                target_url=endpoint,
                answer_text="",
                latency_ms=elapsed,
                error=f"{type(exc).__name__}: {exc}",
            )
