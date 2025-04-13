# api/exploration.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from models.session import GameSession
from models.state import GameState
from services.session_service import SessionService
from services.llm_service import LLMService
from dependencies import get_session
from config.constants import GAME_AREAS

router = APIRouter()
session_service = SessionService()
llm_service = LLMService()

class ActionRequest(BaseModel):
    """Request model for exploration actions"""
    action_type: str
    data: Dict[str, Any]

class ExplorationResponse(BaseModel):
    """Response model for exploration endpoints"""
    description: str
    current_state: str
    current_location: Dict[str, Any]
    allowed_actions: List[str]
    suggested_actions: List[str]
    npcs_present: List[Dict[str, Any]] = []
    items_present: List[Dict[str, Any]] = []
    interactive_objects: List[Dict[str, Any]] = []
    connected_locations: List[Dict[str, str]] = []
    status_updates: Optional[Dict[str, Any]] = None

@router.post("/", response_model=ExplorationResponse)
async def perform_exploration_action(
    action_request: ActionRequest,
    session: GameSession = Depends(get_session)
):
    """Process an exploration action"""
    # Check if we're in the correct state
    if session.state != GameState.EXPLORATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: Session is in {session.state} state, not EXPLORATION"
        )
    
    # Check if the action is allowed
    if not session.is_action_allowed(action_request.action_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action {action_request.action_type} not allowed in {session.state} state"
        )
    
    # Get current location
    current_location = session.world_state.locations.get(session.current_location)
    if not current_location:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Current location not found in world state"
        )
    
    # Mark as visited if first time
    if not current_location.visited:
        current_location.visited = True
    
    # Process the action through the LLM
    player_action = f"{action_request.action_type}: {action_request.data}"
    
    # Get LLM response
    llm_response = await llm_service.process_action(session, player_action)
    
    # Handle the LLM's game engine action
    status_updates = None
    
    if llm_response.get("action") == "changeScene":
        status_updates = await _handle_change_scene(session, llm_response.get("data", {}))
    elif llm_response.get("action") == "skillCheck":
        status_updates = await _handle_skill_check(session, llm_response.get("data", {}))
    elif llm_response.get("action") == "initiateCombat":
        status_updates = await _handle_initiate_combat(session, llm_response.get("data", {}))
    elif llm_response.get("action") == "updatePlayerState":
        status_updates = await _handle_update_player_state(session, llm_response.get("data", {}))
    elif llm_response.get("action") == "updateJournal":
        status_updates = await _handle_update_journal(session, llm_response.get("data", {}))
    elif llm_response.get("action") == "npcInteraction":
        status_updates = await _handle_npc_interaction(session, llm_response.get("data", {}))
    elif llm_response.get("action") == "environmentInteraction":
        status_updates = await _handle_environment_interaction(session, llm_response.get("data", {}))
    
    # Save session state
    session_service.update_session(session)
    
    # Get updated location (it might have changed)
    current_location = session.world_state.locations.get(session.current_location)
    
    # Get NPCs in current location
    npcs_present = [
        {
            "id": npc_id,
            "name": session.world_state.npcs[npc_id].name,
            "description": session.world_state.npcs[npc_id].description,
            "hostile": session.world_state.npcs[npc_id].hostile
        }
        for npc_id in current_location.npcs
        if npc_id in session.world_state.npcs
    ]
    
    # Prepare connected locations
    connected_locations = [
        {
            "id": loc_id,
            "name": session.world_state.locations[loc_id].name
        }
        for loc_id in current_location.connections
        if loc_id in session.world_state.locations
    ]
    
    # Build response
    return {
        "description": llm_response.get("description", ""),
        "current_state": session.state,
        "current_location": {
            "id": current_location.id,
            "name": current_location.name,
            "description": current_location.description,
            "image": current_location.image
        },
        "allowed_actions": session.get_allowed_actions(),
        "suggested_actions": llm_response.get("data", {}).get("suggestedActions", []),
        "npcs_present": npcs_present,
        "items_present": current_location.items,
        "interactive_objects": current_location.interactive_objects,
        "connected_locations": connected_locations,
        "status_updates": status_updates
    }

@router.get("/", response_model=ExplorationResponse)
async def get_exploration_state(
    session: GameSession = Depends(get_session)
):
    """Get the current exploration state"""
    # Check if we're in the correct state
    if session.state != GameState.EXPLORATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: Session is in {session.state} state, not EXPLORATION"
        )
    
    # Get current location
    current_location = session.world_state.locations.get(session.current_location)
    if not current_location:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Current location not found in world state"
        )
    
    # Get NPCs in current location
    npcs_present = [
        {
            "id": npc_id,
            "name": session.world_state.npcs[npc_id].name,
            "description": session.world_state.npcs[npc_id].description,
            "hostile": session.world_state.npcs[npc_id].hostile
        }
        for npc_id in current_location.npcs
        if npc_id in session.world_state.npcs
    ]
    
    # Prepare connected locations
    connected_locations = [
        {
            "id": loc_id,
            "name": session.world_state.locations[loc_id].name
        }
        for loc_id in current_location.connections
        if loc_id in session.world_state.locations
    ]
    
    # Prepare suggested actions based on what's in the location
    suggested_actions = ["Examine Area"]
    
    # Add examine for each object
    for obj in current_location.interactive_objects:
        suggested_actions.append(f"Examine {obj['name']}")
    
    # Add path for each connection
    for conn in connected_locations:
        suggested_actions.append(f"Go to {conn['name']}")
    
    # Add talk for each NPC
    for npc in npcs_present:
        if not npc["hostile"]:
            suggested_actions.append(f"Talk to {npc['name']}")
    
    # Build response
    return {
        "description": current_location.description,
        "current_state": session.state,
        "current_location": {
            "id": current_location.id,
            "name": current_location.name,
            "description": current_location.description,
            "image": current_location.image
        },
        "allowed_actions": session.get_allowed_actions(),
        "suggested_actions": suggested_actions[:5],  # Limit to 5 suggestions
        "npcs_present": npcs_present,
        "items_present": current_location.items,
        "interactive_objects": current_location.interactive_objects,
        "connected_locations": connected_locations,
        "status_updates": None
    }

# Helper functions for handling LLM actions

async def _handle_change_scene(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a scene change action from the LLM"""
    location_id = data.get("locationId")
    
    # Check if location exists
    if location_id not in session.world_state.locations:
        return {"error": f"Location {location_id} not found"}
    
    # Update current location
    session.current_location = location_id
    
    # Update location description if provided
    if "description" in data:
        session.world_state.locations[location_id].description = data["description"]
    
    # Update location image if provided
    if "image" in data:
        session.world_state.locations[location_id].image = data["image"]
    
    # Mark location as visited
    session.world_state.locations[location_id].visited = True
    
    # Update LLM context with new location
    session.llm_context.update_location({
        "id": location_id,
        "name": session.world_state.locations[location_id].name,
        "description": session.world_state.locations[location_id].description
    })
    
    # Add key event for location change
    session.llm_context.add_key_event(f"Moved to {session.world_state.locations[location_id].name}")
    
    return {
        "location_changed": True,
        "new_location": {
            "id": location_id,
            "name": session.world_state.locations[location_id].name
        }
    }

async def _handle_skill_check(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a skill check action from the LLM"""
    # Transition to skill check state
    if not session.transition_to(GameState.SKILL_CHECK):
        return {"error": "Could not transition to SKILL_CHECK state"}
    
    # Set up skill check
    skill = data.get("skill")
    difficulty = data.get("difficulty", 5)
    
    session.skill_check_state.active = True
    session.skill_check_state.skill = skill
    session.skill_check_state.difficulty = difficulty
    session.skill_check_state.success_outcome = data.get("successOutcome")
    session.skill_check_state.failure_outcome = data.get("failureOutcome")
    
    # Calculate player's skill level
    skill_level = session.player.skills.get(skill, 0)
    
    # Add key event for skill check
    session.llm_context.add_key_event(
        f"Attempted {skill} check (difficulty {difficulty}, skill level {skill_level})"
    )
    
    return {
        "skill_check_initiated": True,
        "skill": skill,
        "difficulty": difficulty,
        "player_skill_level": skill_level
    }

async def _handle_initiate_combat(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle combat initiation from the LLM"""
    # Transition to combat state
    if not session.transition_to(GameState.COMBAT):
        return {"error": "Could not transition to COMBAT state"}
    
    # Set up combat
    session.combat_state.active = True
    session.combat_state.enemies = []
    
    # Add enemies
    for enemy_data in data.get("enemies", []):
        enemy_id = enemy_data.get("id")
        count = enemy_data.get("count", 1)
        modifiers = enemy_data.get("modifiers", [])
        
        # Get enemy template from constants
        from config.constants import ENEMY_TYPES
        enemy_template = ENEMY_TYPES.get(enemy_id)
        
        if not enemy_template:
            continue
            
        # Create enemies based on count
        for i in range(count):
            # Create unique ID for each instance
            instance_id = f"{enemy_id}_{i+1}"
            
            # Apply modifiers
            modified_health = enemy_template["health"]
            modified_damage = enemy_template["damage"]
            
            for modifier in modifiers:
                if modifier == "elite":
                    modified_health = int(modified_health * 1.5)
                    modified_damage = int(modified_damage * 1.2)
                elif modifier == "weak":
                    modified_health = int(modified_health * 0.7)
                    modified_damage = int(modified_damage * 0.8)
                elif modifier == "aggressive":
                    modified_damage = int(modified_damage * 1.3)
            
            # Add to combat state
            session.combat_state.enemies.append({
                "id": instance_id,
                "template_id": enemy_id,
                "name": enemy_template["name"],
                "health": modified_health,
                "max_health": modified_health,
                "damage": modified_damage,
                "abilities": enemy_template["abilities"],
                "modifiers": modifiers
            })
    
    # Set up initiative order - player always goes first for now
    session.combat_state.initiative_order = ["player"]
    session.combat_state.initiative_order.extend([enemy["id"] for enemy in session.combat_state.enemies])
    
    # Set ambush state
    session.combat_state.ambush_state = data.get("ambushState", "none")
    
    # If player is surprised, move them to the end of initiative
    if session.combat_state.ambush_state == "player_surprised":
        session.combat_state.initiative_order.remove("player")
        session.combat_state.initiative_order.append("player")
    
    # Set current turn
    session.combat_state.current_turn = session.combat_state.initiative_order[0]
    session.combat_state.round = 1
    
    # Add combat intro to log
    intro_text = data.get("introText", "Combat begins!")
    session.combat_state.add_to_log(intro_text)
    
    # Add key event for combat
    enemy_names = ", ".join([enemy["name"] for enemy in session.combat_state.enemies])
    session.llm_context.add_key_event(f"Entered combat against {enemy_names}")
    
    return {
        "combat_initiated": True,
        "enemies": [
            {
                "id": enemy["id"],
                "name": enemy["name"],
                "health": enemy["health"],
                "max_health": enemy["max_health"]
            }
            for enemy in session.combat_state.enemies
        ],
        "initiative_order": session.combat_state.initiative_order,
        "current_turn": session.combat_state.current_turn,
        "intro_text": intro_text
    }

async def _handle_update_player_state(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle player state updates from the LLM"""
    updates = {}
    
    # Update health
    if "health" in data:
        health_change = data["health"]
        old_health = session.player.health
        
        # Apply health change
        session.player.health += health_change
        
        # Ensure health stays within bounds
        session.player.health = max(0, min(session.player.health, session.player.max_health))
        
        updates["health_change"] = {
            "amount": health_change,
            "old_health": old_health,
            "new_health": session.player.health
        }
        
        # Add key event for significant health changes
        if abs(health_change) >= 10 or health_change <= -5:
            if health_change > 0:
                session.llm_context.add_key_event(f"Healed for {health_change} health")
            else:
                session.llm_context.add_key_event(f"Took {abs(health_change)} damage")
    
    # Update mana
    if "mana" in data:
        mana_change = data["mana"]
        old_mana = session.player.mana
        
        # Apply mana change
        session.player.mana += mana_change
        
        # Ensure mana stays within bounds
        session.player.mana = max(0, min(session.player.mana, session.player.max_mana))
        
        updates["mana_change"] = {
            "amount": mana_change,
            "old_mana": old_mana,
            "new_mana": session.player.mana
        }
    
    # Apply status effects
    if "statusEffects" in data:
        applied_effects = []
        
        for effect_data in data["statusEffects"]:
            effect_id = effect_data.get("id")
            duration = effect_data.get("duration", 3)
            description = effect_data.get("description", "")
            
            # Get effect template from constants
            from config.constants import STATUS_EFFECTS
            effect_template = STATUS_EFFECTS.get(effect_id)
            
            if not effect_template:
                continue
                
            # Create status effect
            from models.player import StatusEffect
            effect = StatusEffect(
                id=effect_id,
                name=effect_template["description"],
                description=description or effect_template["description"],
                duration=duration,
                effect_type=effect_template["effect_type"],
                value=effect_template["value"]
            )
            
            # Apply to player
            session.player.add_status_effect(effect)
            applied_effects.append(effect_id)
            
            # Add key event for status effect
            session.llm_context.add_key_event(f"Gained status effect: {effect.name}")
        
        if applied_effects:
            updates["status_effects_applied"] = applied_effects
    
    # Handle inventory changes
    if "inventoryChanges" in data:
        inventory_updates = []
        
        for change in data["inventoryChanges"]:
            action = change.get("action")
            item_id = change.get("itemId")
            count = change.get("count", 1)
            
            if action == "add":
                # Find item in current location or create a generic one
                item_data = None
                current_location = session.world_state.locations.get(session.current_location)
                
                # Check location items
                if current_location:
                    for item in current_location.items:
                        if item["id"] == item_id:
                            item_data = item
                            # Remove from location if found
                            current_location.items = [i for i in current_location.items if i["id"] != item_id]
                            break
                
                # If not found, create generic item
                if not item_data:
                    item_data = {
                        "id": item_id,
                        "name": item_id.replace("_", " ").title(),
                        "description": "An item you found.",
                        "item_type": "misc",
                        "count": count
                    }
                
                # Create item model
                from models.player import Item
                item = Item(**item_data)
                
                # Add to inventory
                success = session.player.add_item(item)
                
                inventory_updates.append({
                    "action": "add",
                    "item_id": item_id,
                    "success": success
                })
                
                if success:
                    # Add key event for significant items
                    session.llm_context.add_key_event(f"Acquired item: {item.name}")
                
            elif action == "remove":
                success = session.player.remove_item(item_id, count)
                
                inventory_updates.append({
                    "action": "remove",
                    "item_id": item_id,
                    "success": success
                })
                
                if success and count > 0:
                    # Add key event for item loss
                    session.llm_context.add_key_event(f"Lost item: {item_id}")
        
        if inventory_updates:
            updates["inventory_changes"] = inventory_updates
    
    return updates

async def _handle_update_journal(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle journal updates from the LLM"""
    quest_id = data.get("questId")
    
    # Check if quest exists
    if quest_id not in session.world_state.quests:
        return {"error": f"Quest {quest_id} not found"}
    
    quest = session.world_state.quests[quest_id]
    entry_text = data.get("entryText", "")
    
    # Update objectives
    objective_updates = []
    for objective in data.get("objectives", []):
        obj_id = objective.get("id")
        status = objective.get("status")
        
        if obj_id in quest.objectives:
            old_status = quest.objectives[obj_id]
            quest.objectives[obj_id] = status
            
            objective_updates.append({
                "id": obj_id,
                "old_status": old_status,
                "new_status": status
            })
            
            # Add key event for objective completion
            if status == "completed" and old_status != "completed":
                session.llm_context.add_key_event(f"Completed objective: {obj_id}")
    
    # Check if all objectives are completed
    all_completed = all(status == "completed" for status in quest.objectives.values())
    if all_completed and quest.status != "completed":
        quest.status = "completed"
        # Add key event for quest completion
        session.llm_context.add_key_event(f"Completed quest: {quest.name}")
    
    # Activate quest if it's inactive
    if quest.status == "inactive":
        session.world_state.activate_quest(quest_id)
        # Add key event for quest activation
        session.llm_context.add_key_event(f"Started quest: {quest.name}")
    
    return {
        "quest_updated": True,
        "quest_id": quest_id,
        "quest_status": quest.status,
        "objective_updates": objective_updates,
        "entry_text": entry_text
    }

async def _handle_npc_interaction(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle NPC interaction from the LLM"""
    npc_id = data.get("npcId")
    
    # Check if NPC exists
    if npc_id not in session.world_state.npcs:
        return {"error": f"NPC {npc_id} not found"}
    
    # Transition to dialogue state
    if not session.transition_to(GameState.DIALOGUE):
        return {"error": "Could not transition to DIALOGUE state"}
    
    # Set up dialogue
    session.dialogue_state.active = True
    session.dialogue_state.npc_id = npc_id
    
    # Add dialogue to conversation history
    session.dialogue_state.add_exchange(
        speaker=session.world_state.npcs[npc_id].name,
        text=data.get("dialogue", "")
    )
    
    # Set dialogue options
    session.dialogue_state.current_options = data.get("options", [])
    
    # Add key event for important dialogue
    if data.get("mood") == "important":
        npc_name = session.world_state.npcs[npc_id].name
        session.llm_context.add_key_event(f"Important conversation with {npc_name}")
    
    return {
        "dialogue_initiated": True,
        "npc_id": npc_id,
        "npc_name": session.world_state.npcs[npc_id].name,
        "dialogue": data.get("dialogue", ""),
        "options": data.get("options", [])
    }

async def _handle_environment_interaction(session: GameSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle environment interaction from the LLM"""
    interaction_type = data.get("interactionType")
    target_id = data.get("targetId")
    
    # Check if interaction is valid
    current_location = session.world_state.locations.get(session.current_location)
    if not current_location:
        return {"error": "Current location not found"}
    
    # Find the interactive object
    target_object = None
    for obj in current_location.interactive_objects:
        if obj["id"] == target_id:
            target_object = obj
            break
    
    if not target_object:
        return {"error": f"Interactive object {target_id} not found in current location"}
    
    # Check if required items are present
    required_items = data.get("requiredItems", [])
    for item_id in required_items:
        if not session.player.has_item(item_id):
            return {
                "interaction_failed": True,
                "reason": f"Missing required item: {item_id}",
                "description": data.get("description", "")
            }
    
    # Handle item consumption
    if data.get("consumesItems", False):
        for item_id in required_items:
            session.player.remove_item(item_id)
    
    # Process interaction effects
    effects = []
    for effect in data.get("effectsOnActivation", []):
        effect_type = effect.get("type")
        
        if effect_type == "revealPath":
            location_id = effect.get("locationId")
            if location_id and location_id in session.world_state.locations:
                session.world_state.add_connection(session.current_location, location_id)
                effects.append({
                    "type": "path_revealed",
                    "location": session.world_state.locations[location_id].name
                })
                # Add key event for revealing path
                session.llm_context.add_key_event(
                    f"Discovered path to {session.world_state.locations[location_id].name}"
                )
        
        elif effect_type == "modifyEnvironment":
            description = effect.get("description", "")
            if description:
                effects.append({
                    "type": "environment_changed",
                    "description": description
                })
                # Add key event for significant environment changes
                session.llm_context.add_key_event(f"Environment changed: {description}")
        
        elif effect_type == "spawnNPC":
            npc_id = effect.get("npcId")
            if npc_id and npc_id in session.world_state.npcs:
                npc = session.world_state.npcs[npc_id]
                session.world_state.update_npc_location(npc_id, session.current_location)
                effects.append({
                    "type": "npc_appeared",
                    "npc": npc.name
                })

# Add key event for NPC appearance
                session.llm_context.add_key_event(f"{npc.name} appeared")
    
    # Add description to LLM context
    description = data.get("description", "")
    session.llm_context.add_narrative(description)
    
    return {
        "interaction_successful": True,
        "target": target_id,
        "interaction_type": interaction_type,
        "description": description,
        "effects": effects
    }