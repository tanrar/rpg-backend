# dependencies.py
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from typing import Optional

from config.settings import Settings
from models.session import GameSession
from services.session_service import SessionService

@lru_cache()
def get_settings():
    """Return cached settings instance"""
    return Settings()

async def get_session(
    session_id: str,
    session_service: SessionService = Depends(lambda: SessionService())
) -> GameSession:
    """
    Dependency to retrieve a game session by ID
    
    Args:
        session_id: The unique identifier of the session
        session_service: Service to manage game sessions
        
    Returns:
        GameSession: The requested game session
        
    Raises:
        HTTPException: If session not found
    """
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found"
        )
    return session