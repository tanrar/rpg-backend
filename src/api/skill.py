# api/skill.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import random

from models.session import GameSession
from models.state import GameState
from services.session_service import SessionService
from services.llm_service import LLMService
from dependencies import get_session
from config.constants import DIFFICULTY_LEVELS, SKILLS

router = APIRouter()
session_service = SessionService()
llm_service = LLMService()

class SkillCheckRequest(BaseModel):
    """Request model for skill checks"""
    action: str = "attempt"  # attempt, abort, use_item

class SkillCheckResponse(BaseModel):
    """Response model for skill check endpoints"""
    description: str
    current_state: str
    skill: str
    difficulty: int
    roll: Optional[int] = None
    success: Optional[bool] = None
    critical: Optional[bool] = None
    outcome_description: str
    suggested_actions: List[str]
    status_updates: Optional[Dict[str, Any]] = None

@router.post("/", response_model=SkillCheckResponse)
async def perform_skill_check(
    skill_request: SkillCheckRequest,
    session: GameSession = Depends(get_session)
):
    """Process a skill check"""
    # Check if we're in the correct state
    if session.state != GameState.SKILL_CHECK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: Session is in {session.state} state, not SKILL_CHECK"
        )
    
    # Check if skill check is active
    if not session.skill_check_state.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active skill check"
        )
    
    # Handle skill check
    if skill_request.action == "attempt":
        # Get skill check parameters
        skill = session.skill_check_state.skill
        difficulty = session.skill_check_state.difficulty
        
        # Get player's skill level
        skill_level = session.player.skills.get(skill, 0)
        
        # Apply any status effect modifiers
        for effect in session.player.status_effects:
            if effect.effect_type == "skill_modifier" and effect.id == f"{skill}_bonus":
                skill_level += effect.value
        
        # Roll 1d10
        roll = random.randint(1, 10)
        
        # Determine success
        # 1 = critical failure, 2-4 = failure, 5-9 = success, 10 = critical success
        critical = roll == 1 or roll == 10
        success = (roll >= 5) or (roll == 4 and skill_level > 0)  # skill level gives slight bonus
        
        # Get outcome based on result
        if success:
            if critical:
                outcome = session.skill_check_state.success_outcome.get("criticalSuccess", 
                                                                       session.skill_check_state.success_outcome)
            else:
                outcome = session.skill_check_state.success_outcome
        else:
            if critical:
                outcome = session.skill_check_state.failure_outcome.get("criticalFailure", 
                                                                      session.skill_check_state.failure_outcome)
            else:
                outcome = session.skill_check_state.failure_outcome
        
        # Reset skill check state
        session.skill_check_state.active = False
        
        # Add result to LLM context
        result_text = "Critical Success" if success and critical else \
                     "Success" if success else \
                     "Critical Failure" if not success and critical else "Failure"
                     
        session.llm_context.add_key_event(f"{skill.capitalize()} check: {result_text} (rolled {roll}, needed 5)")
        
        # Transition back to exploration by default
        session.transition_to(GameState.EXPLORATION)
        
        # Save session
        session_service.update_session(session)
        
        # Return result
        return {
            "description": f"You attempt the {skill} check...",
            "current_state": session.state,
            "skill": skill,
            "difficulty": difficulty,
            "roll": roll,
            "success": success,
            "critical": critical,
            "outcome_description": outcome.get("description", ""),
            "suggested_actions": outcome.get("suggestedActions", []),
            "status_updates": {
                "skill_check_result": result_text,
                "roll": roll,
                "skill_level": skill_level,
                "difficulty": difficulty
            }
        }
        
    elif skill_request.action == "abort":
        # Cancel the skill check
        session.skill_check_state.active = False
        
        # Transition back to exploration
        session.transition_to(GameState.EXPLORATION)
        
        # Save session
        session_service.update_session(session)
        
        # Return result
        return {
            "description": "You decide not to attempt the skill check.",
            "current_state": session.state,
            "skill": session.skill_check_state.skill,
            "difficulty": session.skill_check_state.difficulty,
            "outcome_description": "Skill check aborted",
            "suggested_actions": ["Examine Area", "Look Around"],
            "status_updates": {
                "skill_check_aborted": True
            }
        }
        
    elif skill_request.action == "use_item":
        # This would be expanded to handle items that can affect skill checks
        # For now, just transition back to inventory state
        
        session.transition_to(GameState.INVENTORY)
        
        # Save session
        session_service.update_session(session)
        
        return {
            "description": "You consider using an item to help with this challenge.",
            "current_state": session.state,
            "skill": session.skill_check_state.skill,
            "difficulty": session.skill_check_state.difficulty,
            "outcome_description": "Checking inventory for helpful items",
            "suggested_actions": [],
            "status_updates": {
                "accessing_inventory": True
            }
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {skill_request.action}"
        )

@router.get("/", response_model=SkillCheckResponse)
async def get_skill_check_state(
    session: GameSession = Depends(get_session)
):
    """Get the current skill check state"""
    # Check if we're in the correct state
    if session.state != GameState.SKILL_CHECK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: Session is in {session.state} state, not SKILL_CHECK"
        )
    
    # Check if skill check is active
    if not session.skill_check_state.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active skill check"
        )
    
    # Get skill check parameters
    skill = session.skill_check_state.skill
    difficulty = session.skill_check_state.difficulty
    
    # Get outcome descriptions
    success_desc = session.skill_check_state.success_outcome.get("description", "")
    failure_desc = session.skill_check_state.failure_outcome.get("description", "")
    
    # Get player's skill level
    skill_level = session.player.skills.get(skill, 0)
    
    # Build an informative description
    skill_desc = SKILLS.get(skill, skill.capitalize())
    difficulty_desc = "Unknown"
    for name, value in DIFFICULTY_LEVELS.items():
        if value == difficulty:
            difficulty_desc = name.capitalize()
            break
    
    description = f"You are attempting a {difficulty_desc} {skill} check. "
    description += f"Your {skill} skill level is {skill_level}. "
    
    # Return current state
    return {
        "description": description,
        "current_state": session.state,
        "skill": skill,
        "difficulty": difficulty,
        "outcome_description": f"Success: {success_desc[:50]}... / Failure: {failure_desc[:50]}...",
        "suggested_actions": ["Attempt", "Abort", "Use Item"]
    }