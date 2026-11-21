"""Configuration for the Zero-Trust Red-Team Legal Auditor (`evaluator_agent`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


AUDITOR_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = AUDITOR_ROOT.parent / "agent"


def _default_corpus_db() -> Path:
    """Resolve the target agent's SQLite index across `.cache` and legacy locations."""
    candidates = [
        AGENT_ROOT / "data" / ".cache" / "bm25_index.sqlite3",
        AGENT_ROOT / "data" / "bm25_index.sqlite3",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


class AuditorSettings(BaseSettings):
    """Settings loaded from `agent_couinter/.env` with fallback to `../agent/.env` for API keys."""

    model_config = SettingsConfigDict(
        env_file=(str(AUDITOR_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Target agent under audit (`agent/`)
    target_agent_url: str = Field(default="http://localhost:8000")
    target_agent_ask_path: str = Field(default="/api/ask")
    target_agent_health_path: str = Field(default="/api/health")
    target_agent_timeout: float = Field(default=90.0, ge=5.0, le=300.0)
    target_agent_answer_style: Literal["concise", "detailed"] = Field(
        default="concise", description="Audit the same answer format end users receive"
    )

    # Independent Auditor LLM
    auditor_llm_provider: Literal["gemini", "openai", "openrouter", "ollama", "mock"] = "gemini"
    auditor_llm_api_key: str = Field(default="")
    auditor_llm_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai/")
    auditor_llm_model: str = Field(default="gemini-3.8-flash")
    auditor_llm_fallback_model: str = Field(default="gemini-2.5-flash", description="Used when primary model 404s")
    auditor_llm_timeout: float = Field(default=60.0, ge=5.0, le=300.0)
    auditor_llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    auditor_llm_max_tokens: int = Field(default=3072)

    # Independent Lex.uz & local corpus verification
    lex_uz_base_url: str = Field(default="https://lex.uz")
    lex_uz_timeout: float = Field(default=15.0)
    local_corpus_db_path: Path = Field(default_factory=_default_corpus_db)
    enable_live_lex_verify: bool = Field(default=True)

    # Storage & server
    data_dir: Path = Field(default=AUDITOR_ROOT / "data")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8001)
    log_level: str = Field(default="INFO")

    @property
    def resolved_corpus_db_path(self) -> Path:
        p = self.local_corpus_db_path
        if not p.is_absolute():
            p = (AUDITOR_ROOT / p).resolve()
        if p.exists():
            return p
        return _default_corpus_db()

    @property
    def auditor_knowledge_db_path(self) -> Path:
        return self.data_dir / "auditor_knowledge.sqlite3"

    @property
    def golden_failures_path(self) -> Path:
        return self.data_dir / "golden_failures.jsonl"

    @property
    def audit_history_path(self) -> Path:
        return self.data_dir / "audit_runs.jsonl"

    @property
    def lex_cache_dir(self) -> Path:
        return self.data_dir / "verifier_cache"

    def resolve_api_key(self) -> str:
        """Return configured auditor key, or seamlessly inherit from `../agent/.env` if unset."""
        key = (self.auditor_llm_api_key or "").strip()
        if key and not key.lower().startswith("your-"):
            return key
        sibling_env = AGENT_ROOT / ".env"
        if sibling_env.exists():
            vals = dotenv_values(sibling_env)
            sibling_key = str(vals.get("LLM_API_KEY") or vals.get("GEMINI_API_KEY") or "").strip()
            if sibling_key and not sibling_key.lower().startswith("your-"):
                return sibling_key
        return ""

    def ensure_directories(self) -> None:
        if not self.data_dir.is_absolute():
            self.data_dir = (AUDITOR_ROOT / self.data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lex_cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> AuditorSettings:
    s = AuditorSettings()
    s.ensure_directories()
    return s
