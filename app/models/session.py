# app/api/sessions.py (update)
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
import uuid

from app.models.session import Session
from app.models.character import Character
from app.models.inventory import Inventory, Item
from app.models.world import WorldState
from app.models.game_state import GameState
from app.services.world_service import WorldService

router = APIRouter()

# Temporary in-memory storage for sessions
# This will be replaced with a proper storage service later
active_sessions = {}

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def create_session(character_data: Dict[str, Any]):
    """Create a new game session."""
    try:
        # Create a character from the provided data
        character = Character(
            name=character_data.get("name", "Adventurer"),
            class_type=character_data.get("class_type", "Courier"),
            origin=character_data.get("origin", "Wasteland-Born"),
            health=50,  # Default values
            max_health=50,
            mana=30,
            max_mana=30,
            skills={
                "perception": 3,
                "technology": 2,
                "strength": 1,
                "charisma": 2
            }
        )
        
        # Create a basic inventory
        inventory = Inventory(
            items=[
                Item(
                    id="medkit",
                    name="Medkit",
                    description="A basic medical kit for treating wounds.",
                    item_type="consumable",
                    effects=[
                        {
                            "type": "healing",
                            "target": "self",
                            "value": 20
                        }
                    ]
                )
            ],
            currency=10
        )
        
        # Create world state using our world service
        world_state = WorldService.initialize_world_state("starting_camp")
        
        # Create the session
        session = Session(
            character=character,
            inventory=inventory,
            world=world_state,
            current_state=GameState.EXPLORATION
        )
        
        # Add initial scene record
        session.add_scene_record(
            scene_type="exploration",
            description="You find yourself at a small survivors' camp. The harsh wasteland stretches in all directions, with only a faint path leading east toward what might be civilization."
        )
        
        # Store the session
        session_id = str(session.id)
        active_sessions[session_id] = session
        
        return {
            "session_id": session_id,
            "message": "Session created successfully",
            "character": character.dict(),
            "current_location": world_state.current_location,
            "current_state": GameState.EXPLORATION.name,
            "theme": world_state.theme.dict() if world_state.theme else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )