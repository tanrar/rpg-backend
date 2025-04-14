# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API configuration
    api_prefix: str = "/api"
    debug: bool = False

    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000"]  # Frontend URL

    # LLM settings
    llm_provider: str = "mock"  # "anthropic", "mock"
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-3-opus-20240229"

    # Storage settings
    storage_type: str = "memory"  # "memory", "file", "database"
    storage_path: Optional[str] = "./data"
    database_url: Optional[str] = None

    # Game settings
    session_timeout_minutes: int = 60
    max_active_sessions: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
