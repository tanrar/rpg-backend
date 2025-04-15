# app/api/exploration/endpoints.py
from fastapi import APIRouter, HTTPException, Depends, status, Path
from typing import Dict, Any, Optional
import logging

from app.models.session import Session
from app.models.game_state import GameState
from app.services.state_service import StateManager
from app.services.world_service import WorldService
from app.api.sessions import active_sessions

from .helpers import llm_adapter, extract_content_from_llm, generate_exploration_prompt, build_scene_context
from .actions import process_llm_actions

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_session(session_id: str) -> Session:
    """
    Get a session by ID and verify it's in the EXPLORATION state.
    
    Args:
        session_id: The session ID
        
    Returns:
        Session: The session object
        
    Raises:
        HTTPException: If session not found or not in EXPLORATION state
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found"
        )
    
    session = active_sessions[session_id]
    session.update_last_active()
    
    if session.current_state != GameState.EXPLORATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is not in EXPLORATION state (current: {session.current_state.name})"
        )
    
    return session

@router.get("/", response_model=Dict[str, Any])
async def get_exploration_state(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get the current exploration state for a session.
    
    Args:
        session_id: The session ID
        
    Returns:
        Dict: Current scene information
    """
    try:
        session = await get_session(session_id)
        
        # Build scene context
        scene_context = build_scene_context(session)
        
        # Get image ID for the location
        image_id = WorldService.get_image_for_location(session.world.current_location)
        
        # Get the most recent narrative text from scene history
        latest_description = "You look around the area."
        if session.scene_history:
            latest_description = session.scene_history[-1].description
        
        return {
            "success": True,
            "description": latest_description,
            "context": scene_context,
            "image": image_id,
            "ui_state": StateManager.get_ui_state(session)
        }
        
    except Exception as e:
        logger.exception(f"Error getting exploration state: {str(e)}")
        return {
            "success": False,
            "error": f"Server error: {str(e)}"
        }

@router.post("/", response_model=Dict[str, Any])
async def perform_action(
    session_id: str = Path(..., description="Session ID"),
    player_input: Dict[str, Any] = None
):
    """
    Process player input during exploration.
    
    Args:
        session_id: The session ID
        player_input: {"text": "Player's input text"}
        
    Returns:
        Dict: Action result and narrative response
    """
    try:
        session = await get_session(session_id)
        
        if not player_input or "text" not in player_input:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No player input provided"
            )
        
        input_text = player_input["text"]
        
        # Generate prompt for the LLM
        prompt = generate_exploration_prompt(
            session=session,
            player_input=input_text,
            include_history=True
        )
        
        # Add player input to scene history
        session.add_scene_record(
            scene_type="player_input",
            description=input_text,
            player_action="custom_input"
        )
        
        # Get response from LLM
        llm_response = await llm_adapter.generate_response(
            prompt=prompt,
            context=session.llm_context[-5:] if session.llm_context else None
        )
        
        # Extract narrative and actions
        narrative, actions = await extract_content_from_llm(llm_response)
        
        # Process any actions the LLM wants to perform
        action_results = None
        if actions and "actions" in actions:
            action_results = await process_llm_actions(session, actions)
        
        # Add narrative to scene history
        session.add_scene_record(
            scene_type="narrative",
            description=narrative
        )
        
        # Save the LLM context for continuity
        session.llm_context.append({
            "role": "user",
            "content": prompt
        })
        session.llm_context.append({
            "role": "assistant",
            "content": llm_response.get("content", "")
        })
        
        # Keep context history manageable but larger than before
        # Retain up to 20 exchanges (10 back-and-forth)
        if len(session.llm_context) > 20:
            session.llm_context = session.llm_context[-20:]
        
        # Get updated scene context
        scene_context = build_scene_context(session)
        
        # Get image ID for the location
        image_id = WorldService.get_image_for_location(session.world.current_location)
        
        return {
            "success": True,
            "description": narrative,
            "context": scene_context,
            "image": image_id,
            "action_results": action_results.get("action_results") if action_results else None,
            "ui_state": StateManager.get_ui_state(session)
        }
        
    except Exception as e:
        logger.exception(f"Error processing player input: {str(e)}")
        return {
            "success": False,
            "error": f"Server error: {str(e)}"
        }