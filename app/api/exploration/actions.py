# app/api/exploration/actions.py
from typing import Dict, Any, Optional
import logging

from app.models.session import Session

logger = logging.getLogger(__name__)

async def modify_inventory(session: Session, action_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add or remove items from player inventory.
    
    Args:
        session: The game session
        action_data: {
            "action": "add" or "remove",
            "item_id": "item_id",
            "count": 1,
            "description": "Optional narrative text explaining the item change"
        }
    """
    item_id = action_data.get("item_id")
    count = action_data.get("count", 1)
    action = action_data.get("action", "add")
    
    if not item_id:
        return {"success": False, "error": "No item specified"}
    
    if action == "add":
        # Logic to add item (ideally this would check if the item exists in a catalog)
        from app.models.inventory import Item
        
        # Simple mock item creation - in a real system, get from a database
        item = Item(
            id=item_id,
            name=item_id.replace("_", " ").title(),
            description=f"A {item_id.replace('_', ' ')}.",
            item_type="miscellaneous"
        )
        
        result = session.inventory.add_item(item)
        return {
            "success": result,
            "message": f"Added {count} {item_id} to inventory" if result else "Inventory full"
        }
    
    elif action == "remove":
        result = session.inventory.remove_item(item_id, count)
        return {
            "success": result,
            "message": f"Removed {count} {item_id} from inventory" if result else f"No {item_id} in inventory"
        }
    
    return {"success": False, "error": "Invalid inventory action"}

async def change_status(session: Session, action_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Change player status (health, mana, etc.)
    
    Args:
        session: The game session
        action_data: {
            "health_change": 0,  # Positive for healing, negative for damage
            "mana_change": 0,
            "description": "Optional narrative text explaining the status change"
        }
    """
    health_change = action_data.get("health_change", 0)
    mana_change = action_data.get("mana_change", 0)
    
    # Apply health change
    if health_change != 0:
        session.character.health += health_change
        session.character.health = max(0, min(session.character.health, session.character.max_health))
    
    # Apply mana change
    if mana_change != 0:
        session.character.mana += mana_change
        session.character.mana = max(0, min(session.character.mana, session.character.max_mana))
    
    return {
        "success": True,
        "health": session.character.health,
        "max_health": session.character.max_health,
        "mana": session.character.mana,
        "max_mana": session.character.max_mana,
    }

async def set_flag(session: Session, action_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set a game flag (for quests, events, etc.)
    
    Args:
        session: The game session
        action_data: {
            "flag": "flag_name",
            "value": True or False,
            "description": "Optional narrative text explaining the flag change"
        }
    """
    flag = action_data.get("flag")
    value = action_data.get("value", True)
    
    if not flag:
        return {"success": False, "error": "No flag specified"}
    
    session.world.global_flags[flag] = value
    
    return {
        "success": True,
        "flag": flag,
        "value": value
    }

async def initiate_combat(session: Session, action_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder for transitioning to combat state
    
    Args:
        session: The game session
        action_data: {
            "enemies": [{"id": "enemy_id", "count": 1}],
            "description": "Combat initiation narrative"
        }
    """
    # This would eventually connect to combat system
    # For now, just record the intention
    return {
        "success": True,
        "combat_requested": True,
        "message": "Combat system not yet implemented"
    }

# Map of action names to handler functions
ACTION_HANDLERS = {
    "modify_inventory": modify_inventory,
    "change_status": change_status,
    "set_flag": set_flag,
    "initiate_combat": initiate_combat
}

async def process_llm_actions(session: Session, llm_actions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process actions requested by the LLM
    
    Args:
        session: The game session
        llm_actions: {
            "actions": [
                {
                    "type": "action_type",
                    "data": {...action-specific data...}
                },
                ...
            ]
        }
    """
    results = []
    
    actions = llm_actions.get("actions", [])
    
    for action in actions:
        action_type = action.get("type")
        action_data = action.get("data", {})
        
        handler = ACTION_HANDLERS.get(action_type)
        if handler:
            try:
                result = await handler(session, action_data)
                results.append({
                    "type": action_type,
                    "success": result.get("success", False),
                    "result": result
                })
            except Exception as e:
                logger.exception(f"Error processing action {action_type}: {str(e)}")
                results.append({
                    "type": action_type,
                    "success": False,
                    "error": str(e)
                })
        else:
            results.append({
                "type": action_type,
                "success": False,
                "error": f"Unknown action type: {action_type}"
            })
    
    return {
        "success": True,
        "action_results": results
    }