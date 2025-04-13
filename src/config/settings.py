# config/settings.py
from pydantic import BaseSettings
from typing import Optional, Dict, Any, List

class Settings(BaseSettings):
    """Application settings managed through environment variables"""
    
    # App settings
    app_name: str = "LLM RPG Game"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # LLM settings
    llm_provider: str = "openai"  # Default, can be changed
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4"
    
    # Storage settings
    storage_type: str = "json"  # Options: json, sqlite, postgres, etc.
    storage_path: str = "./data"
    
    # Game settings
    max_session_age: int = 86400  # 24 hours in seconds
    max_context_history: int = 10  # Number of interactions to keep in context
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"