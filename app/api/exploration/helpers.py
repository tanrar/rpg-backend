# app/api/exploration/helpers.py
from typing import Dict, Any, List, Optional, Tuple
import logging
import json
import re

from app.models.session import Session
from app.services.llm.factory import LLMAdapterFactory
from app.config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()

# Initialize LLM adapter
llm_adapter = LLMAdapterFactory.create_adapter()

async def extract_content_from_llm(llm_response: Dict) -> Tuple[str, Optional[Dict]]:
    """
    Extract narrative content and potential actions from LLM response.
    
    Args:
        llm_response: The raw LLM response
        
    Returns:
        Tuple: (narrative_text, actions_dict or None)
    """
    # Default values
    narrative = "You look around the area."
    actions = None
    
    try:
        if not llm_response.get("success", False):
            return narrative, actions
            
        # Try to parse JSON content
        parsed_response = await llm_adapter.parse_json_response(llm_response)
        
        if parsed_response.get("success", False):
            data = parsed_response.get("data", {})
            
            # Log parsed structure for debugging
            logger.debug(f"Parsed LLM response structure: {json.dumps(data, indent=2)}")
            
            # Extract narrative - look in several common locations
            if "narrative" in data:
                narrative = data["narrative"]
            elif "description" in data:
                narrative = data["description"]
            elif "content" in data:
                narrative = data["content"]
            elif "data" in data and "description" in data["data"]:
                narrative = data["data"]["description"]
            elif "data" in data and "narrative" in data["data"]:
                narrative = data["data"]["narrative"]
            else:
                # Fallback to raw content
                narrative = llm_response.get("content", narrative)
            
            # Extract actions if present
            if "actions" in data:
                actions = data
            elif "data" in data and "actions" in data["data"]:
                actions = data["data"]
                
        else:
            # If JSON parsing fails, use raw content
            raw_content = llm_response.get("content", "")
            narrative = raw_content
            
            # Try to extract JSON from the raw text
            json_pattern = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
            match = json_pattern.search(raw_content)
            if match:
                try:
                    json_str = match.group(1)
                    actions_data = json.loads(json_str)
                    if "actions" in actions_data:
                        actions = actions_data
                except json.JSONDecodeError:
                    pass
            
    except Exception as e:
        logger.exception(f"Error extracting content from LLM response: {str(e)}")
    
    return narrative, actions

def generate_exploration_prompt(
    session: Session, 
    player_input: str,
    include_history: bool = True
) -> str:
    """
    Generate a prompt for the LLM to create a narrative response to player input.
    
    Args:
        session: The game session
        player_input: The player's input text
        include_history: Whether to include interaction history
        
    Returns:
        str: The prompt for the LLM
    """
    character = session.character
    location = session.world.get_location_description(session.world.current_location)
    
    # Build prompt with game state context
    prompt = f"""
    You are the Game Master for an RPG game. The player has given the following input:
    
    PLAYER: {player_input}
    
    Current location: {location.get('name')}
    Location description: {location.get('description')}
    
    Notable NPCs present: {', '.join(location.get('npcs_present', []))}
    Notable objects: {', '.join(location.get('objects', []))}
    Possible exits: {', '.join([exit['destination'].replace('_', ' ').title() for exit in location.get('exits', [])])}
    
    Player character:
    - Name: {character.name}
    - Class: {character.class_type}
    - Origin: {character.origin}
    - Health: {character.health}/{character.max_health}
    - Mana: {character.mana}/{character.max_mana}
    
    Your task is to respond to the player's input in a natural, conversational way, as if you were a human game master. Describe what happens as a result of their action. Be creative, atmospheric, and engaging. Use sensory details and emotion to make the world feel real.

    If the player's actions should have game mechanical effects, you can include those in a structured format. Available actions include:
    
    1. modify_inventory - Add or remove items from the player's inventory
    2. change_status - Modify player health or mana
    3. set_flag - Set a game flag for quest tracking or world state
    4. initiate_combat - Begin a combat encounter (not yet implemented)
    
    Response format:
    {{
        "narrative": "Your descriptive, atmospheric response to the player's action",
        "actions": [
            {{
                "type": "action_type", 
                "data": {{
                    // action-specific data
                }}
            }}
        ]
    }}
    
    The actions array is optional - only include if the player's actions should affect game state.
    """
    
    # Include recent interaction history if requested
    if include_history and session.scene_history:
        # Get the last 10 scene records
        recent_history = session.scene_history[-10:]
        history_text = "\n\n".join([
            f"[{record.scene_type}] "
            f"{record.player_action if record.player_action else 'Game'}: "
            f"{record.description}"
            for record in recent_history
        ])
        
        prompt += f"""
        
        Recent interaction history:
        {history_text}
        """
    
    return prompt
def build_scene_context(session: Session) -> Dict[str, Any]:
    """
    Build detailed context information about the current scene.
    
    Args:
        session: The game session
        
    Returns:
        Dict: Context information for UI
    """
    location = session.world.get_location_description(session.world.current_location)
    
    # Get theme information
    theme = None
    if session.world.theme:
        theme = session.world.theme.dict()
    
    # Extract NPCs and objects for the UI
    npcs = []
    for npc_id in location.get("npcs_present", []):
        if npc_id in session.world.npcs:
            npc_data = session.world.npcs[npc_id]
            npcs.append({
                "id": npc_id,
                "name": npc_data.get("name", npc_id),
                "description": npc_data.get("description", "")
            })
    
    objects = []
    for obj_id in location.get("objects", []):
        objects.append({
            "id": obj_id,
            "name": obj_id.replace("_", " ").title()
        })
    
    # Extract exits
    exits = []
    for exit_data in location.get("exits", []):
        exits.append({
            "destination": exit_data["destination"],
            "description": exit_data["description"],
            "name": exit_data["destination"].replace("_", " ").title()
        })
    
    return {
        "location": location,
        "theme": theme,
        "npcs": npcs,
        "objects": objects,
        "exits": exits,
        "player": {
            "name": session.character.name,
            "class": session.character.class_type,
            "health": session.character.health,
            "maxHealth": session.character.max_health,
            "mana": session.character.mana,
            "maxMana": session.character.max_mana
        }
    }