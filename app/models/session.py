# app/models/session.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4

from app.models.character import Character
from app.models.inventory import Inventory
from app.models.world import WorldState
from app.models.game_state import GameState


class SceneRecord(BaseModel):
    """Model representing a record of scene interaction."""

    timestamp: datetime = Field(default_factory=datetime.now)
    scene_type: str
    description: str
    player_action: Optional[str] = None
    outcome: Optional[str] = None


class Session(BaseModel):
    """Model representing a game session."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    character: Character
    inventory: Inventory
    world: WorldState
    current_state: GameState = GameState.EXPLORATION
    scene_history: List[SceneRecord] = []
    llm_context: List[Dict] = []

    def update_last_active(self):
        """Update the last active timestamp."""
        self.last_active = datetime.now()

    def add_scene_record(
        self,
        scene_type: str,
        description: str,
        player_action: Optional[str] = None,
        outcome: Optional[str] = None,
    ):
        """Add a new scene record to the history."""
        record = SceneRecord(
            scene_type=scene_type,
            description=description,
            player_action=player_action,
            outcome=outcome,
        )
        self.scene_history.append(record)

    def get_recent_history(self, limit: int = 5) -> List[Dict]:
        """Get recent scene history for LLM context."""
        return [
            {
                "timestamp": record.timestamp.isoformat(),
                "scene_type": record.scene_type,
                "description": record.description,
                "player_action": record.player_action,
                "outcome": record.outcome,
            }
            for record in self.scene_history[-limit:]
        ]

    def prepare_llm_context(self, additional_context: Optional[Dict] = None) -> Dict:
        """Prepare context for LLM based on current session state."""
        context = {
            "character": self.character.get_summary(),
            "inventory": self.inventory.get_summary(),
            "location": (
                self.world.get_location_description(self.world.current_location)
                if self.world.current_location
                else None
            ),
            "recent_history": self.get_recent_history(),
            "current_state": self.current_state.name,
        }

        if additional_context:
            context.update(additional_context)

        return context
