# api/inventory.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from models.session import GameSession
from models.player import Item
from models.state import GameState
from services.session_service import SessionService
from services.llm_service import LLMService
from dependencies import get_session

router = APIRouter()
session_service = SessionService()
llm_service = LLMService()

class InventoryActionRequest(BaseModel):
    """Request model for inventory actions"""
    action_type: str  # examine_item, use_item, drop_item, combine_items
    item_id: str
    target_id: Optional[str] = None  # For combine_items or use_item on target

class InventoryResponse(BaseModel):
    """Response model for inventory endpoints"""
    description: str
    current_state: str
    inventory: List[Dict[str, Any]]
    selected_item: Optional[Dict[str, Any]] = None
    available_actions: List[str]
    status_updates: Optional[Dict[str, Any]] = None

@router.post("/", response_model=InventoryResponse)
async def perform_inventory_action(
    action_request: InventoryActionRequest,
    session: GameSession = Depends(get_session)
):
    """Process an inventory action"""
    # Check if we're in the correct state
    if session.state != GameState.INVENTORY:
        # Allow temporary transition to inventory for some actions
        session.transition_to(GameState.INVENTORY)
    
    # Process the action
    action_type = action_request.action_type
    item_id = action_request.item_id
    target_id = action_request.target_id
    status_updates = {}
    description = ""
    
    # Find the item
    item = None
    for i in session.player.inventory:
        if i.id == item_id:
            item = i
            break
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item not found: {item_id}"
        )
    
    if action_type == "examine_item":
        # Just return item details
        description = item.description
        status_updates = {
            "item_examined": item.id
        }
    
    elif action_type == "use_item":
        # Use the item
        
        # Call LLM to determine effect of using the item
        player_action = f"use_item: {item.name}"
        if target_id:
            player_action += f" on {target_id}"
            
        llm_response = await llm_service.process_action(session, player_action)
        
        # Handle the LLM's response
        description = llm_response.get("description", "")
        
        # Process any game engine actions from LLM
        if llm_response.get("action") == "updatePlayerState":
            # Update player state based on item use
            data = llm_response.get("data", {})
            
            # Handle health change
            if "health" in data:
                health_change = data["health"]
                old_health = session.player.health
                
                # Apply health change
                session.player.health += health_change
                
                # Ensure health stays within bounds
                session.player.health = max(0, min(session.player.health, session.player.max_health))
                
                status_updates["health_change"] = {
                    "amount": health_change,
                    "old_health": old_health,
                    "new_health": session.player.health
                }
            
            # Handle mana change
            if "mana" in data:
                mana_change = data["mana"]
                old_mana = session.player.mana
                
                # Apply mana change
                session.player.mana += mana_change
                
                # Ensure mana stays within bounds
                session.player.mana = max(0, min(session.player.mana, session.player.max_mana))
                
                status_updates["mana_change"] = {
                    "amount": mana_change,
                    "old_mana": old_mana,
                    "new_mana": session.player.mana
                }
            
            # Consume the item if it's consumable
            if item.item_type == "consumable":
                session.player.remove_item(item_id)
                status_updates["item_consumed"] = True
        
        # Handle environmental interactions
        elif llm_response.get("action") == "environmentInteraction":
            # Item used on environment
            data = llm_response.get("data", {})
            
            # Check if the interaction was successful
            if data.get("effectsOnActivation"):
                status_updates["interaction_successful"] = True
                
                # Consume the item if needed
                if data.get("consumesItems", False):
                    session.player.remove_item(item_id)
                    status_updates["item_consumed"] = True
            else:
                status_updates["interaction_successful"] = False
    
    elif action_type == "drop_item":
        # Drop the item in the current location
        current_location = session.world_state.locations.get(session.current_location)
        
        if current_location:
            # Create item data for location
            item_data = {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "item_type": item.item_type,
                "properties": item.properties,
                "count": item.count
            }
            
            # Add to location
            current_location.items.append(item_data)
            
            # Remove from inventory
            session.player.remove_item(item_id)
            
            description = f"You drop the {item.name} on the ground."
            status_updates = {
                "item_dropped": item.id
            }
        else:
            description = "Error: Current location not found."
            status_updates = {
                "error": "Current location not found"
            }
    
    elif action_type == "combine_items":
        # Combine items - not implemented in basic version
        # This would need LLM logic to determine valid combinations
        description = "Item combination is not implemented yet."
        status_updates = {
            "error": "Feature not implemented"
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type: {action_type}"
        )
    
    # Save session
    session_service.update_session(session)
    
    # Return response
    return {
        "description": description,
        "current_state": session.state,
        "inventory": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "item_type": item.item_type,
                "count": item.count
            }
            for item in session.player.inventory
        ],
        "selected_item": {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "item_type": item.item_type,
            "count": item.count,
            "properties": item.properties or {}
        } if item else None,
        "available_actions": session.get_allowed_actions(),
        "status_updates": status_updates
    }

@router.get("/", response_model=InventoryResponse)
async def get_inventory(
    session: GameSession = Depends(get_session)
):
    """Get the player's inventory"""
    # Temporarily transition to inventory if needed
    original_state = session.state
    if session.state != GameState.INVENTORY:
        session.transition_to(GameState.INVENTORY)
    
    # Return inventory
    return {
        "description": "You check your inventory.",
        "current_state": session.state,
        "inventory": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "item_type": item.item_type,
                "count": item.count
            }
            for item in session.player.inventory
        ],
        "available_actions": session.get_allowed_actions(),
        "status_updates": {
            "previous_state": original_state
        }
    }

@router.get("/item/{item_id}", response_model=InventoryResponse)
async def get_item_details(
    item_id: str,
    session: GameSession = Depends(get_session)
):
    """Get details about a specific item"""
    # Find the item
    item = None
    for i in session.player.inventory:
        if i.id == item_id:
            item = i
            break
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item not found: {item_id}"
        )
    
    # Temporarily transition to inventory if needed
    original_state = session.state
    if session.state != GameState.INVENTORY:
        session.transition_to(GameState.INVENTORY)
    
    # Return item details
    return {
        "description": item.description,
        "current_state": session.state,
        "inventory": [
            {
                "id": i.id,
                "name": i.name,
                "description": i.description,
                "item_type": i.item_type,
                "count": i.count
            }
            for i in session.player.inventory
        ],
        "selected_item": {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "item_type": item.item_type,
            "count": item.count,
            "properties": item.properties or {}
        },
        "available_actions": [
            "examine_item", 
            "use_item", 
            "drop_item", 
            ("combine_items" if len(session.player.inventory) > 1 else None)
        ],
        "status_updates": {
            "previous_state": original_state
        }
    }