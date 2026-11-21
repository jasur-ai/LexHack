"""Centralized configuration for Haqli v2.1 + Recognition Engine v1.0 backend."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    demo_mode: bool = True
    public_base_url: str = "http://localhost:8002"
    cors_origins: str = "http://localhost:5173,http://localhost:8002,http://127.0.0.1:5173"

    # One persistent directory (e.g. a Render disk) for the SQLite DB, uploads and PDFs. Explicit
    # DATABASE_URL / UPLOAD_DIR / PDF_DIR values still win when they are set.
    storage_dir: Path | None = None
    database_url: str = "sqlite+aiosqlite:///./data/haqli.db"

    jwt_secret: str = "haqli-dev-jwt-secret-change-in-production-32chars"
    jwt_ttl_minutes: int = 60
    fernet_key: str = ""
    fernet_key_id: str = "k1"
    ed25519_private_key_b64: str = ""

    telegram_bot_token: str = ""
    telegram_bot_username: str = "haqli_bot"
    advocate_invite_codes: str = "HAQLI-ADV-2026,DEMO-ADV"

    allow_web_guests: bool = True  # browsers outside Telegram get a private per-device guest account

    # Lex.uz legal AI agent (`agent/`) used by the "AI yurist" chat
    agent_base_url: str = "http://127.0.0.1:8000"
    agent_timeout_sec: float = 75.0
    agent_user_questions_per_hour: int = 40

    llm_provider: Literal["null", "openai", "gemini", "anthropic", "local"] = "null"
    llm_api_key: str = ""
    llm_model: str = "gemini-3.8-flash"
    llm_base_url: str = ""
    llm_timeout_sec: float = 20.0

    # Storage & Retention
    upload_dir: Path = Field(default=Path("./data/uploads"))
    pdf_dir: Path = Field(default=Path("./data/pdfs"))
    recognition_retention_hours: int = 24
    max_upload_mb: int = 10
    max_audio_mb: int = 8
    max_pdf_pages: int = 20
    max_image_megapixels: int = 40

    # Recognition Engine v1.0 toggles & limits
    recognition_ocr: Literal["off", "paddle", "tesseract", "vision", "auto"] = "auto"
    recognition_stt: Literal["off", "local", "cloud", "auto"] = "auto"
    whisper_model: str = "large-v3"
    whisper_compute_type: str = "int8"
    cloud_stt_url: str = ""
    cloud_stt_api_key: str = ""
    clamav_host: str = ""

    recognition_ocr_concurrency: int = 2
    recognition_stt_concurrency: int = 1
    recognition_user_jobs_per_hour: int = 20
    recognition_user_max_concurrent: int = 5
    recognition_default_timezone: str = "Asia/Tashkent"

    # Server image quality gate defaults (§5.1)
    quality_blur_ok: float = 80.0
    quality_blur_warn: float = 40.0
    quality_brightness_min: float = 60.0
    quality_brightness_max: float = 210.0
    quality_contrast_min: float = 35.0
    quality_min_resolution: int = 900
    quality_max_glare_ratio: float = 0.08
    quality_max_skew_deg: float = 12.0

    # Uzbekistan vehicle plate regex patterns (marked needs_review like legal data, §6.1)
    uz_plate_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\b\d{2}\s?[A-Z]\s?\d{3}\s?[A-Z]{2}\b",
            r"\b\d{2}\s?\d{3}\s?[A-Z]{3}\b",
        ]
    )
    uz_plate_patterns_status: str = "needs_review"

    @property
    def legal_data_dir(self) -> Path:
        return Path(__file__).resolve().parent / "legal_data"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def advocate_codes_set(self) -> set[str]:
        return {c.strip().upper() for c in self.advocate_invite_codes.split(",") if c.strip()}

    @model_validator(mode="after")
    def _apply_storage_dir(self) -> "Settings":
        if self.storage_dir is not None:
            root = Path(self.storage_dir)
            explicit = self.model_fields_set
            if "database_url" not in explicit:
                self.database_url = f"sqlite+aiosqlite:///{(root / 'haqli.db').as_posix()}"
            if "upload_dir" not in explicit:
                self.upload_dir = root / "uploads"
            if "pdf_dir" not in explicit:
                self.pdf_dir = root / "pdfs"
        return self

    @property
    def sqlite_path(self) -> Path | None:
        if not self.database_url.startswith("sqlite"):
            return None
        raw = self.database_url.split(":///", 1)[1] if ":///" in self.database_url else ""
        return Path(raw) if raw and raw != ":memory:" else None

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        db_file = self.sqlite_path
        if db_file is not None:
            db_file.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
