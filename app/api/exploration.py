# app/api/exploration.py
from fastapi import APIRouter, HTTPException, Depends, status, Path
from typing import Dict, Any, Optional, List
import logging
import json
import re

from app.models.session import Session
from app.models.game_state import GameState
from app.services.state_service import StateManager, InvalidActionError, StateTransitionError
from app.services.llm.factory import LLMAdapterFactory
from app.services.world_service import WorldService
from app.config.settings import Settings

# Import our in-memory sessions (this will be replaced with a proper session service later)
from app.api.sessions import active_sessions

router = APIRouter()
logger = logging.getLogger(__name__)
settings = Settings()

# Initialize LLM adapter
llm_adapter = LLMAdapterFactory.create_adapter()

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

async def extract_description_from_llm(llm_response: Dict) -> tuple:
    """
    Extract description and suggested actions from LLM response.
    
    Args:
        llm_response: The raw LLM response
        
    Returns:
        tuple: (description, suggested_actions)
    """
    # Default values
    description = "You look around the area."
    suggested_actions = []
    
    try:
        if not llm_response.get("success", False):
            return description, suggested_actions
            
        # Try to parse JSON content
        parsed_response = await llm_adapter.parse_json_response(llm_response)
        
        if parsed_response.get("success", False):
            data = parsed_response.get("data", {})
            
            # Log parsed structure for debugging
            logger.debug(f"Parsed LLM response structure: {json.dumps(data, indent=2)}")
            
            # Handle different response formats based on the structure
            if "action" in data and "data" in data:
                # Handle structured action response (e.g., narrativeResponse, changeScene)
                action_data = data.get("data", {})
                
                if "description" in action_data:
                    description = action_data["description"]
                elif "narration" in action_data:
                    description = action_data["narration"]
                
                if "suggestedActions" in action_data:
                    suggested_actions = action_data["suggestedActions"]
            elif "description" in data:
                # Direct description field
                description = data["description"]
                if "suggestedActions" in data:
                    suggested_actions = data["suggestedActions"]
            else:
                # Fallback to raw content
                description = llm_response.get("content", description)
        else:
            # If JSON parsing fails, use raw content and try to extract meaningful text
            raw_content = llm_response.get("content", "")
            description = raw_content
            
            # Try to clean up raw content if it contains JSON-like text
            json_pattern = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
            match = json_pattern.search(raw_content)
            if match:
                try:
                    json_str = match.group(1)
                    json_data = json.loads(json_str)
                    
                    if "data" in json_data and "description" in json_data["data"]:
                        description = json_data["data"]["description"]
                    if "data" in json_data and "suggestedActions" in json_data["data"]:
                        suggested_actions = json_data["data"]["suggestedActions"]
                except json.JSONDecodeError:
                    # If JSON extraction fails, keep using raw content
                    pass
    except Exception as e:
        logger.exception(f"Error extracting description from LLM response: {str(e)}")
    
    return description, suggested_actions

async def format_suggested_actions(raw_suggestions: List) -> List[Dict]:
    """
    Format raw suggested actions into structured action objects.
    
    Args:
        raw_suggestions: List of raw action suggestions
        
    Returns:
        List[Dict]: Formatted action objects
    """
    formatted_actions = []
    
    for suggestion in raw_suggestions:
        if not isinstance(suggestion, str):
            # If it's already a dict, use it as is
            if isinstance(suggestion, dict):
                formatted_actions.append(suggestion)
            continue
            
        # Default action
        action = {
            "type": "custom",
            "description": suggestion,
            "target": ""
        }
        
        # Try to parse the action type from the suggestion text
        suggestion_lower = suggestion.lower()
        
        if any(word in suggestion_lower for word in ["examine", "investigate", "look at", "inspect"]):
            action["type"] = "examine"
            for word in ["examine", "investigate", "look at", "inspect"]:
                if word in suggestion_lower:
                    action["target"] = suggestion_lower.replace(word, "").strip()
                    break
                    
        elif any(word in suggestion_lower for word in ["talk to", "speak with", "approach", "ask"]):
            action["type"] = "talk"
            for word in ["talk to", "speak with", "approach", "ask"]:
                if word in suggestion_lower:
                    action["target"] = suggestion_lower.replace(word, "").strip()
                    break
                    
        elif any(word in suggestion_lower for word in ["use", "interact with", "activate"]):
            action["type"] = "interact"
            for word in ["use", "interact with", "activate"]:
                if word in suggestion_lower:
                    action["target"] = suggestion_lower.replace(word, "").strip()
                    break
                    
        elif any(word in suggestion_lower for word in ["go to", "move to", "travel to", "head to"]):
            action["type"] = "move"
            for word in ["go to", "move to", "travel to", "head to"]:
                if word in suggestion_lower:
                    action["target"] = suggestion_lower.replace(word, "").strip()
                    action["destination"] = action["target"]
                    break
        
        formatted_actions.append(action)
    
    return formatted_actions

@router.get("/", response_model=Dict[str, Any])
async def get_exploration_state(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get the current exploration state for a session.
    
    Args:
        session_id: The session ID
        
    Returns:
        Dict: Current location, available actions, and UI state
    """
    try:
        session = await get_session(session_id)
        
        # Get location description
        location_description = session.world.get_location_description(session.world.current_location)
        
        # Get theme information
        theme = None
        if session.world.theme:
            theme = session.world.theme.dict()
        
        # Get image ID for the location
        image_id = WorldService.get_image_for_location(session.world.current_location)
        
        # Get available actions
        available_actions = get_available_actions(session)
        
        # Generate a narrative description for the current location
        location_prompt = f"""
        Describe the current location: {location_description.get('name')}
        
        Details:
        {location_description.get('description')}
        
        Region: {location_description.get('region')}
        
        Available exits: {', '.join([exit['destination'] for exit in location_description.get('exits', [])])}
        
        NPCs present: {', '.join(location_description.get('npcs_present', []))}
        
        Notable objects: {', '.join(location_description.get('objects', []))}
        
        First visit: {not location_description.get('visited_before', False)}
        
        Respond with a detailed, atmospheric description in JSON format:
        {{
            "action": "narrativeResponse",
            "data": {{
                "description": "Your detailed description here...",
                "suggestedActions": ["Action 1", "Action 2", "Action 3", "Action 4", "Action 5"]
            }}
        }}
        """
        
        llm_response = await llm_adapter.generate_response(
            prompt=location_prompt,
            context=session.llm_context[-5:] if session.llm_context else None
        )
        
        # Extract description and suggested actions
        narrative, raw_suggested = await extract_description_from_llm(llm_response)
        
        # Format suggested actions
        suggested_actions = await format_suggested_actions(raw_suggested)
        
        # Get default suggested actions if none were provided
        if not suggested_actions:
            default_actions = get_default_actions(session)
            suggested_actions = await format_suggested_actions(default_actions)
        
        # Save to session context
        session.llm_context.append({
            "role": "user",
            "content": location_prompt
        })
        session.llm_context.append({
            "role": "assistant", 
            "content": llm_response.get("content", "")
        })
        
        # Limit context size
        if len(session.llm_context) > 10:
            session.llm_context = session.llm_context[-10:]
        
        return {
            "success": True,
            "description": narrative,
            "location": location_description,
            "theme": theme,
            "image": image_id,
            "available_actions": available_actions,
            "suggested_actions": suggested_actions,
            "ui_state": StateManager.get_ui_state(session)
        }
    except Exception as e:
        logger.exception(f"Error getting exploration state: {str(e)}")
        return {
            "success": False,
            "error": f"Server error: {str(e)}"
        }

@router.post("/", response_model=Dict[str, Any])
async def perform_exploration_action(
    session_id: str = Path(..., description="Session ID"),
    action: Dict[str, Any] = None
):
    """
    Perform an action in exploration mode.
    
    Args:
        session_id: The session ID
        action: The action to perform, containing action_type and data
        
    Returns:
        Dict: Action result, narrative description, and UI state updates
    """
    try:
        session = await get_session(session_id)
        
        if not action:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No action provided"
            )
            
        action_type = action.get("action_type")
        action_data = action.get("data", {})
        logger.info(f"Performing action: {action_type} with data: {action_data}")
        if not action_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No action_type specified in action"
            )
            
        # Process the action using the state manager
        action_result = await StateManager.process_action(
            session=session,
            action_type=action_type,
            action_data=action_data
        )
        
        if not action_result.get("success", False):
            return {
                "success": False,
                "error": action_result.get("error", "Unknown error processing action")
            }
            
        # Check if we need to transition to another state
        if "transition_to" in action_result:
            target_state = action_result["transition_to"]
            transition_context = action_result.get("transition_context", {})
            
            try:
                transition_result = await StateManager.transition_state(
                    session=session,
                    new_state=target_state,
                    context=transition_context
                )
                
                # Return the transition result directly
                return {
                    "success": True,
                    "action_result": action_result,
                    "transition_result": transition_result,
                    "ui_state": StateManager.get_ui_state(session)
                }
                
            except StateTransitionError as e:
                return {
                    "success": False,
                    "error": str(e)
                }
                
        # If no transition, prepare LLM context based on the action result
        llm_context = session.prepare_llm_context({
            "action_type": action_type,
            "action_data": action_data,
            "action_result": action_result
        })
        
        # Generate narrative response from LLM
        narrative_prompt = generate_narrative_prompt(
            session=session,
            action_type=action_type,
            action_data=action_data,
            action_result=action_result
        )
        
        llm_response = await llm_adapter.generate_response(
            prompt=narrative_prompt,
            context=session.llm_context[-5:] if session.llm_context else None
        )
        
        # Extract description and suggested actions
        narrative, raw_suggested = await extract_description_from_llm(llm_response)
        
        # Format suggested actions
        suggested_actions = await format_suggested_actions(raw_suggested)
        
        # Save the LLM context for continuity
        session.llm_context.append({
            "role": "user",
            "content": narrative_prompt
        })
        session.llm_context.append({
            "role": "assistant",
            "content": llm_response.get("content", "")
        })
        
        # Keep context history manageable
        if len(session.llm_context) > 10:
            session.llm_context = session.llm_context[-10:]
            
        # Get available actions based on the current location
        available_actions = get_available_actions(session)
        
        # Get theme information
        theme = None
        if session.world.theme:
            theme = session.world.theme.dict()
        
        # Get image ID for the location
        image_id = WorldService.get_image_for_location(session.world.current_location)
        
        # Get default suggested actions if none were provided
        if not suggested_actions:
            default_actions = get_default_actions(session)
            suggested_actions = await format_suggested_actions(default_actions)
        
        return {
            "success": True,
            "description": narrative,
            "location": session.world.get_location_description(session.world.current_location),
            "theme": theme,
            "image": image_id,
            "available_actions": available_actions,
            "suggested_actions": suggested_actions,
            "ui_state": StateManager.get_ui_state(session)
        }
        
    except InvalidActionError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.exception(f"Error processing exploration action: {str(e)}")
        return {
            "success": False,
            "error": f"Server error: {str(e)}"
        }

def generate_narrative_prompt(
    session: Session, 
    action_type: str, 
    action_data: Dict[str, Any],
    action_result: Dict[str, Any]
) -> str:
    """
    Generate a prompt for the LLM to create a narrative description.
    
    Args:
        session: The game session
        action_type: The type of action performed
        action_data: Data for the action
        action_result: Result of the action
        
    Returns:
        str: The prompt for the LLM
    """
    character = session.character
    location = session.world.get_location_description(session.world.current_location)
    
    # Construct prompt based on action type
    if action_type == "move":
        destination = action_data.get("destination", "unknown location")
        prompt = f"""
        The player has moved to {destination}.
        
        Location description: {location.get('description')}
        
        Create a vivid, immersive description of this location. Include sensory details and interesting elements the player might notice. 
        
        Also describe any NPCs that are immediately visible: {', '.join(location.get('npcs_present', []))}
        
        Notable objects here: {', '.join(location.get('objects', []))}
        
        Response should be in JSON format:
        {{
            "action": "changeScene",
            "data": {{
                "locationId": "{session.world.current_location}",
                "description": "Your detailed, atmospheric description here...",
                "image": "{location.get('image', '')}",
                "suggestedActions": ["Action 1", "Action 2", "Action 3"]
            }}
        }}
        """
        
    elif action_type == "examine":
        target = action_data.get("target", "the surroundings")
        prompt = f"""
        The player is examining {target} in {location.get('name')}.
        
        Target description: {action_result.get('description', f'A {target}.')}
        
        Create a detailed, insightful description of what the player discovers when examining {target}. Include interesting details, potential clues, or useful information.
        
        Response should be in JSON format:
        {{
            "action": "narrativeResponse",
            "data": {{
                "description": "Your detailed examination description here...",
                "suggestedActions": ["Action 1", "Action 2", "Action 3"]
            }}
        }}
        """
        
    elif action_type == "interact":
        target = action_data.get("target", "object")
        interaction = action_data.get("interaction", "use")
        prompt = f"""
        The player is attempting to {interaction} the {target} in {location.get('name')}.
        
        Interaction result: {action_result.get('description', f'You {interaction} the {target}.')}
        
        Describe what happens when the player {interaction}s the {target}. Include any effects, changes to the environment, or outcomes of this interaction.
        
        Response should be in JSON format:
        {{
            "action": "environmentInteraction",
            "data": {{
                "interactionType": "{interaction}",
                "targetId": "{target}",
                "description": "Your detailed interaction description here...",
                "effectsOnActivation": [
                    {{
                        "type": "description",
                        "description": "Any effect that occurs"
                    }}
                ],
                "suggestedActions": ["Action 1", "Action 2", "Action 3"]
            }}
        }}
        """
        
    elif action_type == "talk":
        npc = action_data.get("npc", "person")
        prompt = f"""
        The player is attempting to talk to {npc} in {location.get('name')}.
        
        Create an introduction to the conversation with {npc}. Describe their appearance, demeanor, and initial reaction to the player.
        
        Response should be in JSON format:
        {{
            "action": "npcInteraction",
            "data": {{
                "npcId": "{npc}",
                "dialogue": "NPC's opening dialogue here...",
                "mood": "Choose a mood: friendly, neutral, suspicious, hostile, etc.",
                "options": [
                    {{
                        "text": "Conversation option 1",
                        "intent": "Ask about location"
                    }},
                    {{
                        "text": "Conversation option 2",
                        "intent": "Ask about self"
                    }},
                    {{
                        "text": "Conversation option 3",
                        "intent": "Leave conversation"
                    }}
                ],
                "description": "Your detailed interaction description here...",
                "suggestedActions": ["Ask about X", "Inquire about Y", "Leave conversation"]
            }}
        }}
        """
    else:
        # Generic prompt for other action types
        prompt = f"""
        The player performed a {action_type} action in {location.get('name')}.
        
        Action details: {action_data}
        
        Result: {action_result.get('description', f'You performed a {action_type} action.')}
        
        Describe what happens when the player performs this action. Be detailed and atmospheric.
        
        Response should be in JSON format:
        {{
            "action": "narrativeResponse",
            "data": {{
                "description": "Your detailed description here...",
                "suggestedActions": ["Action 1", "Action 2", "Action 3"]
            }}
        }}
        """
    
    # Add context about the character and world
    context = f"""
    Player Character:
    - Name: {character.name}
    - Class: {character.class_type}
    - Origin: {character.origin}
    - Level: {character.level}
    
    You are the narrative engine for an RPG game. Your response should be atmospheric and immersive, but also include the structured JSON format requested.
    """
    
    return f"{context}\n\n{prompt}"

def get_available_actions(session: Session) -> Dict[str, Any]:
    """
    Get available actions based on the current location.
    
    Args:
        session: The game session
        
    Returns:
        Dict: Available actions categorized by type
    """
    location = session.world.get_location_description(session.world.current_location)
    
    # Extract movement options
    movement_actions = []
    for exit in location.get("exits", []):
        movement_actions.append({
            "type": "move",
            "destination": exit["destination"],
            "description": f"Go to {exit['destination'].replace('_', ' ').title()}"
        })
    
    # Extract examination options
    examine_actions = []
    for obj in location.get("objects", []):
        examine_actions.append({
            "type": "examine",
            "target": obj,
            "description": f"Examine the {obj}"
        })
    
    # Add location examination
    examine_actions.append({
        "type": "examine",
        "target": "surroundings",
        "description": "Look around"
    })
    
    # Extract interaction options
    interact_actions = []
    for obj in location.get("objects", []):
        interact_actions.append({
            "type": "interact",
            "target": obj,
            "interaction": "use",
            "description": f"Use the {obj}"
        })
    
    # Extract talk options
    talk_actions = []
    for npc in location.get("npcs_present", []):
        talk_actions.append({
            "type": "talk",
            "npc": npc,
            "description": f"Talk to {npc}"
        })
    
    return {
        "move": movement_actions,
        "examine": examine_actions,
        "interact": interact_actions,
        "talk": talk_actions
    }

def get_default_actions(session: Session) -> List[str]:
    """
    Get default suggested actions when LLM doesn't provide any.
    
    Args:
        session: The game session
        
    Returns:
        List: Default suggested actions
    """
    location = session.world.get_location_description(session.world.current_location)
    
    default_actions = ["Look around"]
    
    # Add a movement option if available
    if location.get("exits", []):
        exit_info = location["exits"][0]
        default_actions.append(f"Go to {exit_info['destination'].replace('_', ' ').title()}")
    
    # Add an object interaction if available
    if location.get("objects", []):
        obj = location["objects"][0]
        default_actions.append(f"Examine the {obj}")
    
    # Add an NPC interaction if available
    if location.get("npcs_present", []):
        npc = location["npcs_present"][0]
        default_actions.append(f"Talk to {npc}")
    
    return default_actions