# app/api/exploration.py
from fastapi import APIRouter, HTTPException, Depends, status, Path
from typing import Dict, Any, Optional
import logging

from app.models.session import Session
from app.models.game_state import GameState
from app.services.state_service import (
    StateManager,
    InvalidActionError,
    StateTransitionError,
)
from app.services.llm.factory import LLMAdapterFactory
from app.config.settings import Settings

# Import our in-memory sessions (this will be replaced with a proper session service later)
from app.api.sessions import active_sessions

router = APIRouter()
logger = logging.getLogger(__name__)
settings = Settings()

# Initialize LLM adapter
llm_adapter = LLMAdapterFactory.create_adapter(
    provider=settings.llm_provider,
    config={"api_key": settings.anthropic_api_key, "model": settings.anthropic_model},
)


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
            detail=f"Session with ID {session_id} not found",
        )

    session = active_sessions[session_id]
    session.update_last_active()

    if session.current_state != GameState.EXPLORATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is not in EXPLORATION state (current: {session.current_state.name})",
        )

    return session


@router.post("/", response_model=Dict[str, Any])
async def perform_exploration_action(
    session_id: str = Path(..., description="Session ID"), action: Dict[str, Any] = None
):
    """
    Perform an action in exploration mode.

    Args:
        session_id: The session ID
        action: The action to perform, containing action_type and data

    Returns:
        Dict: Action result, narrative description, and UI state updates
    """
    session = await get_session(session_id)

    if not action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No action provided"
        )

    action_type = action.get("action_type")
    action_data = action.get("data", {})

    if not action_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No action_type specified in action",
        )

    try:
        # Process the action using the state manager
        action_result = await StateManager.process_action(
            session=session, action_type=action_type, action_data=action_data
        )

        if not action_result.get("success", False):
            return {
                "success": False,
                "error": action_result.get("error", "Unknown error processing action"),
            }

        # Check if we need to transition to another state
        if "transition_to" in action_result:
            target_state = action_result["transition_to"]
            transition_context = action_result.get("transition_context", {})

            try:
                transition_result = await StateManager.transition_state(
                    session=session, new_state=target_state, context=transition_context
                )

                # Return the transition result directly
                return {
                    "success": True,
                    "action_result": action_result,
                    "transition_result": transition_result,
                    "ui_state": StateManager.get_ui_state(session),
                }

            except StateTransitionError as e:
                return {"success": False, "error": str(e)}

        # If no transition, prepare LLM context based on the action result
        llm_context = session.prepare_llm_context(
            {
                "action_type": action_type,
                "action_data": action_data,
                "action_result": action_result,
            }
        )

        # Generate narrative response from LLM
        narrative_prompt = generate_narrative_prompt(
            session=session,
            action_type=action_type,
            action_data=action_data,
            action_result=action_result,
        )

        llm_response = await llm_adapter.generate_response(
            prompt=narrative_prompt,
            context=session.llm_context[-5:] if session.llm_context else None,
        )

        if not llm_response.get("success", False):
            logger.error(f"LLM error: {llm_response.get('error')}")
            # Fall back to basic description if LLM fails
            narrative = action_result.get(
                "description",
                f"You {action_type} the {action_data.get('target', 'object')}.",
            )
        else:
            # Parse the LLM response
            parsed_response = await llm_adapter.parse_json_response(llm_response)

            if parsed_response.get("success", False):
                narrative_data = parsed_response.get("data", {})
                # Update session with LLM-generated data if available
                if "action" in narrative_data and "data" in narrative_data:
                    # Process LLM-directed game engine actions here
                    # This could update the world state, trigger events, etc.
                    handle_llm_directed_action(session, narrative_data)

                narrative = narrative_data.get(
                    "narration", llm_response.get("content", "")
                )
            else:
                # If JSON parsing fails, use the raw content
                narrative = llm_response.get("content", "")

        # Save the LLM context for continuity
        session.llm_context.append({"role": "user", "content": narrative_prompt})
        session.llm_context.append(
            {"role": "assistant", "content": llm_response.get("content", "")}
        )

        # Keep context history manageable
        if len(session.llm_context) > 10:
            session.llm_context = session.llm_context[-10:]

        # Get available actions based on the current location
        available_actions = get_available_actions(session)

        # Get suggested actions based on the context
        suggested_actions = get_suggested_actions(
            session=session, action_result=action_result, llm_response=llm_response
        )

        return {
            "success": True,
            "description": narrative,
            "location": session.world.get_location_description(
                session.world.current_location
            ),
            "available_actions": available_actions,
            "suggested_actions": suggested_actions,
            "ui_state": StateManager.get_ui_state(session),
        }

    except InvalidActionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"Error processing exploration action: {str(e)}")
        return {"success": False, "error": f"Server error: {str(e)}"}


@router.get("/", response_model=Dict[str, Any])
async def get_exploration_state(session_id: str = Path(..., description="Session ID")):
    """
    Get the current exploration state for a session.

    Args:
        session_id: The session ID

    Returns:
        Dict: Current location, available actions, and UI state
    """
    session = await get_session(session_id)

    # Get location description
    location_description = session.world.get_location_description(
        session.world.current_location
    )

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
    """

    llm_response = await llm_adapter.generate_response(
        prompt=location_prompt,
        context=session.llm_context[-5:] if session.llm_context else None,
    )

    if not llm_response.get("success", False):
        # Fall back to basic description if LLM fails
        narrative = location_description.get("description", "You look around the area.")
    else:
        # Try to parse structured data, or use the content directly
        parsed_response = await llm_adapter.parse_json_response(llm_response)

        if parsed_response.get("success", False):
            narrative_data = parsed_response.get("data", {})
            narrative = narrative_data.get(
                "description", llm_response.get("content", "")
            )
        else:
            narrative = llm_response.get("content", "")

    # Get suggested actions
    suggested_actions = get_suggested_actions(session=session)

    return {
        "success": True,
        "description": narrative,
        "location": location_description,
        "available_actions": available_actions,
        "suggested_actions": suggested_actions,
        "ui_state": StateManager.get_ui_state(session),
    }


def generate_narrative_prompt(
    session: Session,
    action_type: str,
    action_data: Dict[str, Any],
    action_result: Dict[str, Any],
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
                ]
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


def handle_llm_directed_action(session: Session, narrative_data: Dict[str, Any]):
    """
    Handle actions directed by the LLM response.

    This function processes structured commands from the LLM that request
    game engine actions like updating the world state.

    Args:
        session: The game session
        narrative_data: Structured data from the LLM response
    """
    action_type = narrative_data.get("action")
    action_data = narrative_data.get("data", {})

    if action_type == "changeScene":
        # The LLM is suggesting a scene description update
        # We don't actually change location, just update description
        location_id = action_data.get("locationId")
        if location_id and location_id == session.world.current_location:
            # Update suggested actions for the current location if provided
            suggested_actions = action_data.get("suggestedActions", [])
            # We could store these for later use
            pass

    elif action_type == "updatePlayerState":
        # The LLM is suggesting updates to player state
        # We would validate and apply appropriate changes
        # For now, just log it
        logger.info(f"LLM suggested player state update: {action_data}")

    elif action_type == "environmentInteraction":
        # The LLM is describing effects of an environment interaction
        # We could update world state based on this
        logger.info(f"LLM suggested environment interaction: {action_data}")

    # Other action types could be handled here


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
        movement_actions.append(
            {
                "type": "move",
                "destination": exit["destination"],
                "description": exit["description"],
            }
        )

    # Extract examination options
    examine_actions = []
    for obj in location.get("objects", []):
        examine_actions.append(
            {"type": "examine", "target": obj, "description": f"Examine the {obj}"}
        )

    # Add location examination
    examine_actions.append(
        {"type": "examine", "target": "surroundings", "description": "Look around"}
    )

    # Extract interaction options
    interact_actions = []
    for obj in location.get("objects", []):
        interact_actions.append(
            {
                "type": "interact",
                "target": obj,
                "interaction": "use",
                "description": f"Use the {obj}",
            }
        )

    # Extract talk options
    talk_actions = []
    for npc in location.get("npcs_present", []):
        talk_actions.append(
            {"type": "talk", "npc": npc, "description": f"Talk to {npc}"}
        )

    return {
        "move": movement_actions,
        "examine": examine_actions,
        "interact": interact_actions,
        "talk": talk_actions,
    }


def get_suggested_actions(
    session: Session,
    action_result: Optional[Dict[str, Any]] = None,
    llm_response: Optional[Dict[str, Any]] = None,
) -> list[Dict[str, Any]]:
    """
    Get contextually appropriate suggested actions.

    Args:
        session: The game session
        action_result: Result of the last action
        llm_response: Response from the LLM

    Returns:
        List: Suggested actions
    """
    # Default suggestions based on location
    suggested = []

    # If we have LLM-suggested actions, use those
    if llm_response and llm_response.get("success", False):
        parsed = llm_adapter.parse_json_response(llm_response)
        if parsed.get("success", False):
            data = parsed.get("data", {})

            # Extract suggestions from various action types
            if "data" in data:
                action_data = data.get("data", {})

                if "suggestedActions" in action_data:
                    # Convert string suggestions to action objects
                    for suggestion in action_data["suggestedActions"]:
                        # Try to parse the suggestion into an action
                        # This is simplified - would need more sophisticated parsing in production
                        if isinstance(suggestion, str):
                            if "examine" in suggestion.lower():
                                target = (
                                    suggestion.lower().replace("examine", "").strip()
                                )
                                suggested.append(
                                    {
                                        "type": "examine",
                                        "target": target,
                                        "description": suggestion,
                                    }
                                )
                            elif (
                                "talk" in suggestion.lower()
                                or "speak" in suggestion.lower()
                            ):
                                parts = (
                                    suggestion.lower()
                                    .replace("talk to", "")
                                    .replace("speak with", "")
                                    .strip()
                                )
                                suggested.append(
                                    {
                                        "type": "talk",
                                        "npc": parts,
                                        "description": suggestion,
                                    }
                                )
                            elif (
                                "use" in suggestion.lower()
                                or "interact" in suggestion.lower()
                            ):
                                parts = (
                                    suggestion.lower()
                                    .replace("use", "")
                                    .replace("interact with", "")
                                    .strip()
                                )
                                suggested.append(
                                    {
                                        "type": "interact",
                                        "target": parts,
                                        "interaction": "use",
                                        "description": suggestion,
                                    }
                                )
                            elif (
                                "go" in suggestion.lower()
                                or "move" in suggestion.lower()
                                or "return" in suggestion.lower()
                            ):
                                # This is very simplified - would need better parsing
                                for exit_info in session.world.locations[
                                    session.world.current_location
                                ].exits:
                                    if (
                                        exit_info.destination_id.lower()
                                        in suggestion.lower()
                                    ):
                                        suggested.append(
                                            {
                                                "type": "move",
                                                "destination": exit_info.destination_id,
                                                "description": suggestion,
                                            }
                                        )
                                        break
                            else:
                                # Generic suggestion
                                suggested.append(
                                    {"type": "custom", "description": suggestion}
                                )

    # If we don't have enough suggestions, add some defaults
    if len(suggested) < 3:
        available = get_available_actions(session)

        # Add a movement suggestion if available
        if available["move"] and len(suggested) < 3:
            for move in available["move"]:
                if not any(
                    s.get("type") == "move"
                    and s.get("destination") == move["destination"]
                    for s in suggested
                ):
                    suggested.append(move)
                    break

        # Add an examine suggestion if available
        if available["examine"] and len(suggested) < 3:
            for examine in available["examine"]:
                if not any(
                    s.get("type") == "examine" and s.get("target") == examine["target"]
                    for s in suggested
                ):
                    suggested.append(examine)
                    break

        # Add a talk suggestion if available
        if available["talk"] and len(suggested) < 3:
            for talk in available["talk"]:
                if not any(
                    s.get("type") == "talk" and s.get("npc") == talk["npc"]
                    for s in suggested
                ):
                    suggested.append(talk)
                    break

    # Limit to at most 5 suggestions
    return suggested[:5]
