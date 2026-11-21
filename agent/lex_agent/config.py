"""Centralized configuration for the Lex.uz Legal AI Agent."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=4096)

    # Embeddings settings
    embedding_provider: Literal["openai", "local", "hash"] = "local"
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    embedding_api_key: str = Field(default="")
    embedding_base_url: str = Field(default="")

    # Qdrant vector store settings
    qdrant_mode: Literal["local", "remote", "memory"] = "local"
    qdrant_path: Path = Field(default=Path("./data/qdrant"))
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str = Field(default="")
    qdrant_collection: str = Field(default="lex_uz_legislation")

    # Cross-encoder reranker
    reranker_enabled: bool = Field(default=True)
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3")

    # Live Lex.uz fetching
    lex_uz_base_url: str = Field(default="https://lex.uz")
    lex_uz_timeout: float = Field(default=25.0)
    lex_uz_rate_limit_rps: float = Field(default=2.0)
    lex_uz_use_playwright: bool = Field(default=False)
    lex_uz_enable_live_fallback: bool = Field(default=True)

    # Agentic pipeline controls
    agent_max_hops: int = Field(default=3, ge=1, le=6)
    agent_top_k: int = Field(default=12, ge=1, le=50)
    agent_rerank_top_k: int = Field(default=8, ge=1, le=30)
    agent_strict_citation_mode: bool = Field(default=True)

    # Storage & server
    data_dir: Path = Field(default=Path("./data"))
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    @property
    def bm25_db_path(self) -> Path:
        return self.data_dir / "bm25_index.sqlite3"

    @property
    def doc_registry_path(self) -> Path:
        return self.data_dir / "document_registry.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "lex_cache"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.qdrant_mode == "local":
            self.qdrant_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
