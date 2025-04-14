# app/services/state_factory.py
from typing import Dict, Any
import logging

from app.models.game_state import GameState
from app.services.state_service import StateManager
from app.models.session import Session

logger = logging.getLogger(__name__)


class StateServiceFactory:
    """
    Factory for initializing and managing state handlers.

    This class is responsible for registering all action handlers with the StateManager.
    """

    @classmethod
    async def initialize(cls):
        """Initialize all state handlers."""
        logger.info("Initializing state handlers")

        # Register exploration handlers
        cls._register_exploration_handlers()

        # Register combat handlers
        cls._register_combat_handlers()

        # Register dialogue handlers
        cls._register_dialogue_handlers()

        # Register other state handlers
        cls._register_inventory_handlers()
        cls._register_skill_check_handlers()
        cls._register_character_sheet_handlers()
        cls._register_menu_handlers()

        logger.info("State handlers initialized")

    @classmethod
    def _register_exploration_handlers(cls):
        """Register handlers for the EXPLORATION state."""

        # Movement handler
        async def handle_move(
            session: Session, action_data: Dict[str, Any]
        ) -> Dict[str, Any]:
            destination = action_data.get("destination")
            if not destination:
                return {"success": False, "error": "No destination specified"}

            result = session.world.change_location(destination)
            if not result.get("success", False):
                return result

            return {
                "success": True,
                "description": f"Moved to {destination}",
                "location": session.world.get_location_description(destination),
                "outcome": "Successfully changed location",
            }

        # Examine handler
        async def handle_examine(
            session: Session, action_data: Dict[str, Any]
        ) -> Dict[str, Any]:
            target = action_data.get("target")
            if not target:
                return {"success": False, "error": "No target specified"}

            # This would normally query the world model for object details
            # For now, just return a placeholder response
            return {
                "success": True,
                "description": f"You examine the {target} closely.",
                "outcome": f"Discovered details about {target}",
            }

        # Interact handler
        async def handle_interact(
            session: Session, action_data: Dict[str, Any]
        ) -> Dict[str, Any]:
            target = action_data.get("target")
            interaction = action_data.get("interaction", "use")

            if not target:
                return {"success": False, "error": "No target specified"}

            # This would normally handle object interactions
            # For now, just return a placeholder response
            return {
                "success": True,
                "description": f"You {interaction} the {target}.",
                "outcome": f"Interacted with {target}",
            }

        # Talk handler
        async def handle_talk(
            session: Session, action_data: Dict[str, Any]
        ) -> Dict[str, Any]:
            npc = action_data.get("npc")
            if not npc:
                return {"success": False, "error": "No NPC specified"}

            # In a real implementation, this would transition to dialogue state
            # For now, just prepare for transition
            return {
                "success": True,
                "description": f"You approach {npc} to start a conversation.",
                "transition_to": GameState.DIALOGUE,
                "transition_context": {
                    "npc_id": npc,
                    "description": f"Starting conversation with {npc}",
                },
            }

        # Register the handlers
        StateManager.register_action_handler(GameState.EXPLORATION, "move", handle_move)
        StateManager.register_action_handler(
            GameState.EXPLORATION, "examine", handle_examine
        )
        StateManager.register_action_handler(
            GameState.EXPLORATION, "interact", handle_interact
        )
        StateManager.register_action_handler(GameState.EXPLORATION, "talk", handle_talk)

    @classmethod
    def _register_combat_handlers(cls):
        """Register handlers for the COMBAT state."""
        # Add combat handlers here
        # For example: attack, use_ability, defend, etc.
        pass

    @classmethod
    def _register_dialogue_handlers(cls):
        """Register handlers for the DIALOGUE state."""
        # Add dialogue handlers here
        # For example: respond, ask_question, etc.
        pass

    @classmethod
    def _register_inventory_handlers(cls):
        """Register handlers for the INVENTORY state."""
        # Add inventory handlers here
        pass

    @classmethod
    def _register_skill_check_handlers(cls):
        """Register handlers for the SKILL_CHECK state."""
        # Add skill check handlers here
        pass

    @classmethod
    def _register_character_sheet_handlers(cls):
        """Register handlers for the CHARACTER_SHEET state."""
        # Add character sheet handlers here
        pass

    @classmethod
    def _register_menu_handlers(cls):
        """Register handlers for the MENU state."""
        # Add menu handlers here
        pass
