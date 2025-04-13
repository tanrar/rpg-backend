# api/character.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from models.session import GameSession
from models.state import GameState
from services.session_service import SessionService
from dependencies import get_session
from config.constants import CHARACTER_CLASSES, CHARACTER_ORIGINS, SKILLS

router = APIRouter()
session_service = SessionService()

class CharacterUpdateRequest(BaseModel):
    """Request model for character updates"""
    action_type: str  # level_up, assign_points
    skill_id: Optional[str] = None
    ability_id: Optional[str] = None

class CharacterResponse(BaseModel):
    """Response model for character endpoints"""
    name: str
    character_class: str
    origin: str
    level: int
    experience: int
    health: int
    max_health: int
    mana: int
    max_mana: int
    skills: Dict[str, int]
    abilities: List[Dict[str, Any]]
    active_abilities: List[str]
    status_effects: List[Dict[str, Any]]
    available_actions: List[str]
    class_info: Dict[str, Any]
    origin_info: Dict[str, Any]
    can_level_up: bool
    status_updates: Optional[Dict[str, Any]] = None

@router.post("/", response_model=CharacterResponse)
async def update_character(
    update_request: CharacterUpdateRequest,
    session: GameSession = Depends(get_session)
):
    """Update character stats, level up, etc."""
    # Check if we're in the correct state
    if session.state != GameState.CHARACTER_SHEET:
        # Allow temporary transition
        session.transition_to(GameState.CHARACTER_SHEET)
    
    # Process the action
    action_type = update_request.action_type
    status_updates = {}
    
    if action_type == "level_up":
        # Level up the character
        # In a full game, this would check XP thresholds
        
        # Simple implementation - increment level
        old_level = session.player.level
        session.player.level += 1
        
        # Increase max health and mana
        old_max_health = session.player.max_health
        old_max_mana = session.player.max_mana
        
        # Basic scaling - adjust as needed
        session.player.max_health += 5
        session.player.max_mana += 3
        
        # Restore health and mana on level up
        session.player.health = session.player.max_health
        session.player.mana = session.player.max_mana
        
        # Update status
        status_updates = {
            "level_up": {
                "old_level": old_level,
                "new_level": session.player.level,
                "health_increase": session.player.max_health - old_max_health,
                "mana_increase": session.player.max_mana - old_max_mana
            }
        }
        
        # Add key event
        session.llm_context.add_key_event(f"Leveled up to level {session.player.level}")
    
    elif action_type == "assign_points":
        # Assign skill points
        skill_id = update_request.skill_id
        
        if not skill_id or skill_id not in SKILLS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid skill: {skill_id}"
            )
        
        # In a full game, this would check available skill points
        # For simplicity, we'll just increment the skill
        old_skill = session.player.skills.get(skill_id, 0)
        session.player.skills[skill_id] = old_skill + 1
        
        # Update status
        status_updates = {
            "skill_increase": {
                "skill": skill_id,
                "old_value": old_skill,
                "new_value": session.player.skills[skill_id]
            }
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type: {action_type}"
        )
    
    # Save session
    session_service.update_session(session)
    
    # Get class and origin info
    class_info = CHARACTER_CLASSES.get(
        session.player.character_class.lower(), 
        {"description": "Unknown class"}
    )
    
    origin_info = CHARACTER_ORIGINS.get(
        session.player.origin.lower(), 
        {"description": "Unknown origin"}
    )
    
    # Return response
    return {
        "name": session.player.name,
        "character_class": session.player.character_class,
        "origin": session.player.origin,
        "level": session.player.level,
        "experience": session.player.experience,
        "health": session.player.health,
        "max_health": session.player.max_health,
        "mana": session.player.mana,
        "max_mana": session.player.max_mana,
        "skills": session.player.skills,
        "abilities": [
            {
                "id": ability.id,
                "name": ability.name,
                "description": ability.description,
                "mana_cost": ability.mana_cost,
                "cooldown": ability.cooldown,
                "current_cooldown": ability.current_cooldown
            }
            for ability in session.player.abilities
        ],
        "active_abilities": session.player.active_abilities,
        "status_effects": [
            {
                "id": effect.id,
                "name": effect.name,
                "description": effect.description,
                "duration": effect.duration
            }
            for effect in session.player.status_effects
        ],
        "available_actions": session.get_allowed_actions(),
        "class_info": class_info,
        "origin_info": origin_info,
        "can_level_up": True,  # Simplified - in a full game, this would check XP
        "status_updates": status_updates
    }

@router.get("/", response_model=CharacterResponse)
async def get_character_sheet(
    session: GameSession = Depends(get_session)
):
    """Get the character sheet"""
    # Temporarily transition to character sheet if needed
    if session.state != GameState.CHARACTER_SHEET:
        session.transition_to(GameState.CHARACTER_SHEET)
    
    # Get class and origin info
    class_info = CHARACTER_CLASSES.get(
        session.player.character_class.lower(), 
        {"description": "Unknown class"}
    )
    
    origin_info = CHARACTER_ORIGINS.get(
        session.player.origin.lower(), 
        {"description": "Unknown origin"}
    )
    
    # Return character sheet
    return {
        "name": session.player.name,
        "character_class": session.player.character_class,
        "origin": session.player.origin,
        "level": session.player.level,
        "experience": session.player.experience,
        "health": session.player.health,
        "max_health": session.player.max_health,
        "mana": session.player.mana,
        "max_mana": session.player.max_mana,
        "skills": session.player.skills,
        "abilities": [
            {
                "id": ability.id,
                "name": ability.name,
                "description": ability.description,
                "mana_cost": ability.mana_cost,
                "cooldown": ability.cooldown,
                "current_cooldown": ability.current_cooldown
            }
            for ability in session.player.abilities
        ],
        "active_abilities": session.player.active_abilities,
        "status_effects": [
            {
                "id": effect.id,
                "name": effect.name,
                "description": effect.description,
                "duration": effect.duration
            }
            for effect in session.player.status_effects
        ],
        "available_actions": session.get_allowed_actions(),
        "class_info": class_info,
        "origin_info": origin_info,
        "can_level_up": True,  # Simplified - in a full game, this would check XP
        "status_updates": None
    }