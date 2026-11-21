"""Centralized configuration for the Lex.uz Legal AI Agent."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env` (cwd first, then the agent folder)."""

    model_config = SettingsConfigDict(
        env_file=(str(AGENT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM settings
    llm_provider: Literal["openai", "openrouter", "gemini", "ollama", "mock"] = "gemini"
    llm_api_key: str = Field(default="", description="API key for the configured LLM provider")
    gemini_api_key: str = Field(default="", description="Optional alias for Gemini API key")
    llm_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai/")
    llm_model: str = Field(default="gemini-3.8-flash", description="Primary reasoning model")
    llm_fast_model: str = Field(default="gemini-3.8-flash", description="Fast model for query decomposition/routing")
    llm_fallback_model: str = Field(
        default="gemini-2.5-flash",
        description="Used automatically when the primary model is unavailable (HTTP 404) for this API key",
    )
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=4096)
    llm_thinking_level: str = Field(
        default="auto",
        description="Gemini 3+/4 thinking level: auto|minimal|low|medium|high (auto = lowest latency the model supports)",
    )
    llm_request_timeout: float = Field(default=45.0, description="Hard cap (s) for one LLM call")
    llm_first_token_timeout: float = Field(
        default=20.0, description="If no streamed token arrives in this time, answer extractively instead"
    )

    # Embeddings settings
    embedding_provider: Literal["openai", "local", "hash"] = "hash"
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    embedding_api_key: str = Field(default="")
    embedding_base_url: str = Field(default="")

    # Qdrant vector store settings
    qdrant_mode: Literal["local", "remote", "memory"] = "local"
    qdrant_path: Path = Field(default=AGENT_ROOT / "data" / "qdrant")
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str = Field(default="")
    qdrant_collection: str = Field(default="lex_uz_legislation")

    # Second-stage reranker
    reranker_enabled: bool = Field(default=True)
    reranker_backend: Literal["auto", "trained", "heuristic", "cross_encoder"] = Field(
        default="auto",
        description="auto = bundled trained model when present, else the heuristic; cross_encoder needs the [ml] extra",
    )
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", description="Cross-encoder (only for cross_encoder)")

    # Live Lex.uz fetching
    lex_uz_base_url: str = Field(default="https://lex.uz")
    lex_uz_timeout: float = Field(default=25.0)
    lex_uz_rate_limit_rps: float = Field(default=2.0)
    lex_uz_use_playwright: bool = Field(default=False)
    lex_uz_enable_live_fallback: bool = Field(default=True)
    lex_uz_live_fallback_timeout: float = Field(default=4.0, description="Max seconds spent on a live lex.uz lookup")

    # Agentic pipeline controls
    agent_max_hops: int = Field(default=3, ge=1, le=6)
    agent_top_k: int = Field(default=12, ge=1, le=50)
    agent_rerank_top_k: int = Field(default=8, ge=1, le=30)
    agent_strict_citation_mode: bool = Field(default=True)
    answer_style_default: Literal["concise", "detailed"] = "concise"
    answer_cache_ttl_sec: int = Field(default=6 * 3600, ge=0)
    answer_cache_size: int = Field(default=512, ge=0)
    vector_search_mode: Literal["auto", "on", "off"] = Field(
        default="auto", description="auto = dense search only when real neural embeddings are configured"
    )

    # Security
    admin_token: str = Field(default="", description="Required in X-Admin-Token for /api/ingest/* when set")
    allow_open_ingest: bool = Field(default=False, description="Dev only: allow ingest endpoints without a token")
    cors_origins: str = Field(default="*", description="Comma separated list of allowed origins")

    # Storage & server
    data_dir: Path = Field(default=AGENT_ROOT / "data")
    corpus_dir: Path = Field(default=AGENT_ROOT / "data" / "corpus")
    index_dir: Path | None = Field(
        default=None,
        description="Where the generated SQLite index lives (default: <data_dir>/.cache, rebuilt automatically)",
    )
    auto_build_index: bool = Field(default=True, description="Build the bundled offline index on startup if needed")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    @property
    def resolved_index_dir(self) -> Path:
        return self.index_dir or (self.data_dir / ".cache")

    @property
    def bm25_db_path(self) -> Path:
        return self.resolved_index_dir / "bm25_index.sqlite3"

    @property
    def doc_registry_path(self) -> Path:
        return self.resolved_index_dir / "document_registry.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "lex_cache"

    @property
    def llm_key_configured(self) -> bool:
        key = (self.llm_api_key or self.gemini_api_key or "").strip().lower()
        return bool(key) and key not in {"mock", "changeme", "none", "your-api-key", "sk-xxx"} and not key.startswith("your-")

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_index_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
