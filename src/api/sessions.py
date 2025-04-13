# api/sessions.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Optional

from models.session import GameSession
from models.state import GameState
from services.session_service import SessionService
from dependencies import get_settings, get_session

router = APIRouter()
session_service = SessionService()

class CreateSessionRequest(BaseModel):
    """Request model for creating a new session"""
    player_name: str
    character_class: str
    origin: str

class SessionResponse(BaseModel):
    """Response model for session endpoints"""
    session_id: str
    player: Dict
    state: str
    current_location: str
    allowed_actions: List[str]
    allowed_transitions: List[str]

class SessionListResponse(BaseModel):
    """Response model for listing sessions"""
    sessions: List[Dict]

@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest):
    """Create a new game session"""
    # Validate character class and origin
    from config.constants import CHARACTER_CLASSES, CHARACTER_ORIGINS
    
    if request.character_class.lower() not in CHARACTER_CLASSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid character class. Valid options: {list(CHARACTER_CLASSES.keys())}"
        )
        
    if request.origin.lower() not in CHARACTER_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid origin. Valid options: {list(CHARACTER_ORIGINS.keys())}"
        )
    
    # Create session
    session = session_service.create_session(
        player_name=request.player_name,
        character_class=request.character_class.lower(),
        origin=request.origin.lower()
    )
    
    # Return response
    return {
        "session_id": session.session_id,
        "player": {
            "name": session.player.name,
            "class": session.player.character_class,
            "origin": session.player.origin,
            "level": session.player.level,
            "health": session.player.health,
            "max_health": session.player.max_health,
            "mana": session.player.mana,
            "max_mana": session.player.max_mana
        },
        "state": session.state,
        "current_location": session.current_location,
        "allowed_actions": session.get_allowed_actions(),
        "allowed_transitions": [state.value for state in session.get_allowed_transitions()]
    }

@router.get("/", response_model=SessionListResponse)
async def list_sessions():
    """List all active sessions"""
    sessions = session_service.list_sessions()
    return {"sessions": sessions}

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_by_id(session: GameSession = Depends(get_session)):
    """Get a specific session by ID"""
    return {
        "session_id": session.session_id,
        "player": {
            "name": session.player.name,
            "class": session.player.character_class,
            "origin": session.player.origin,
            "level": session.player.level,
            "health": session.player.health,
            "max_health": session.player.max_health,
            "mana": session.player.mana,
            "max_mana": session.player.max_mana
        },
        "state": session.state,
        "current_location": session.current_location,
        "allowed_actions": session.get_allowed_actions(),
        "allowed_transitions": [state.value for state in session.get_allowed_transitions()]
    }

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session: GameSession = Depends(get_session)):
    """End a game session"""
    success = session_service.end_session(session.session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end session"
        )