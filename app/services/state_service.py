# app/services/state_service.py
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from app.models.game_state import GameState
from app.models.session import Session, SceneRecord

logger = logging.getLogger(__name__)


class StateTransitionError(Exception):
    """Exception raised when an invalid state transition is attempted."""

    pass


class InvalidActionError(Exception):
    """Exception raised when an invalid action is attempted in the current state."""

    pass


class StateManager:
    """
    Manages game state transitions and action validation.

    This service is responsible for:
    1. Validating state transitions
    2. Validating actions within states
    3. Handling the state transition process
    4. Providing state-specific context for LLM
    5. Managing scene history
    """

    # Define valid transitions between states
    VALID_TRANSITIONS = {
        GameState.EXPLORATION: [
            GameState.COMBAT,
            GameState.DIALOGUE,
            GameState.SKILL_CHECK,
            GameState.INVENTORY,
            GameState.CHARACTER_SHEET,
            GameState.MENU,
        ],
        GameState.COMBAT: [GameState.EXPLORATION, GameState.INVENTORY],
        GameState.DIALOGUE: [GameState.EXPLORATION, GameState.SKILL_CHECK],
        GameState.SKILL_CHECK: [
            GameState.EXPLORATION,
            GameState.COMBAT,
            GameState.DIALOGUE,
        ],
        GameState.INVENTORY: [
            GameState.EXPLORATION,
            GameState.COMBAT,
            GameState.DIALOGUE,
        ],
        GameState.CHARACTER_SHEET: [GameState.EXPLORATION],
        GameState.MENU: [GameState.EXPLORATION],
    }

    # Define valid actions for each state
    VALID_ACTIONS = {
        GameState.EXPLORATION: ["move", "examine", "interact", "talk"],
        GameState.COMBAT: ["attack", "use_ability", "use_item", "defend", "flee"],
        GameState.DIALOGUE: ["respond", "ask_question", "end_conversation"],
        GameState.SKILL_CHECK: ["roll", "use_ability", "use_item"],
        GameState.INVENTORY: ["examine_item", "use_item", "equip_item", "drop_item"],
        GameState.CHARACTER_SHEET: ["view_stats", "level_up", "assign_points"],
        GameState.MENU: ["save", "load", "settings", "exit"],
    }

    # Action handlers by state and action type
    ACTION_HANDLERS = {}

    @classmethod
    def register_action_handler(cls, state: GameState, action_type: str, handler_func):
        """
        Register a handler function for a specific state and action type.

        Args:
            state: The game state
            action_type: The type of action
            handler_func: Function to handle the action, taking (session, action_data) parameters
        """
        if state not in cls.ACTION_HANDLERS:
            cls.ACTION_HANDLERS[state] = {}

        cls.ACTION_HANDLERS[state][action_type] = handler_func
        logger.info(f"Registered handler for {state.name}.{action_type}")

    @classmethod
    def can_transition(cls, from_state: GameState, to_state: GameState) -> bool:
        """
        Check if transition from current state to target state is valid.

        Args:
            from_state: The current game state
            to_state: The target game state

        Returns:
            bool: True if transition is valid, False otherwise
        """
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])

    @classmethod
    def get_valid_actions(cls, state: GameState) -> List[str]:
        """
        Get list of valid action types for the current state.

        Args:
            state: The game state

        Returns:
            List[str]: List of valid action types
        """
        return cls.VALID_ACTIONS.get(state, [])

    @classmethod
    def get_valid_transitions(cls, state: GameState) -> List[GameState]:
        """
        Get list of valid states that can be transitioned to from the current state.

        Args:
            state: The game state

        Returns:
            List[GameState]: List of valid target states
        """
        return cls.VALID_TRANSITIONS.get(state, [])

    @classmethod
    async def transition_state(
        cls,
        session: Session,
        new_state: GameState,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Transition from the current state to a new state.

        Args:
            session: The game session
            new_state: The target game state
            context: Optional context data for the transition

        Returns:
            Dict: Result of the transition including updated session state

        Raises:
            StateTransitionError: If the transition is invalid
        """
        if not cls.can_transition(session.current_state, new_state):
            raise StateTransitionError(
                f"Cannot transition from {session.current_state.name} to {new_state.name}"
            )

        # Record the state transition
        previous_state = session.current_state
        transition_description = context.get(
            "description",
            f"Transitioning from {previous_state.name} to {new_state.name}",
        )

        # Add scene record for the transition
        session.add_scene_record(
            scene_type=f"transition_{previous_state.name.lower()}_to_{new_state.name.lower()}",
            description=transition_description,
            player_action=context.get("player_action"),
            outcome=context.get("outcome"),
        )

        # Update the session state
        session.current_state = new_state
        session.update_last_active()

        # Prepare initial context for the new state
        initial_context = await cls.prepare_state_context(
            session, additional_context=context
        )

        logger.info(
            f"Transitioned session {session.id} from {previous_state.name} to {new_state.name}"
        )

        return {
            "success": True,
            "previous_state": previous_state.name,
            "current_state": new_state.name,
            "context": initial_context,
            "allowed_actions": cls.get_valid_actions(new_state),
            "allowed_transitions": [
                state.name for state in cls.get_valid_transitions(new_state)
            ],
        }

    @classmethod
    async def process_action(
        cls, session: Session, action_type: str, action_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process an action within the current state.

        Args:
            session: The game session
            action_type: The type of action to perform
            action_data: Data for the action

        Returns:
            Dict: Result of the action

        Raises:
            InvalidActionError: If the action is invalid for the current state
        """
        # Validate the action type for the current state
        if action_type not in cls.get_valid_actions(session.current_state):
            raise InvalidActionError(
                f"Action '{action_type}' is not valid in state {session.current_state.name}"
            )

        # Get the handler for this state and action type
        state_handlers = cls.ACTION_HANDLERS.get(session.current_state, {})
        handler = state_handlers.get(action_type)

        if not handler:
            logger.warning(
                f"No handler registered for {session.current_state.name}.{action_type}"
            )
            return {
                "success": False,
                "error": f"No handler available for {action_type} in {session.current_state.name}",
            }

        # Execute the handler
        try:
            result = await handler(session, action_data)

            # Update session last active time
            session.update_last_active()

            # Log the action
            if result.get("success", False) and not result.get(
                "suppress_history", False
            ):
                session.add_scene_record(
                    scene_type=f"{session.current_state.name.lower()}_{action_type}",
                    description=result.get("description", f"Performed {action_type}"),
                    player_action=action_type,
                    outcome=result.get("outcome"),
                )

            return result

        except Exception as e:
            logger.exception(
                f"Error processing action {action_type} in state {session.current_state.name}"
            )
            return {"success": False, "error": f"Error processing action: {str(e)}"}

    @classmethod
    async def prepare_state_context(
        cls, session: Session, additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare context information specific to the current state.

        Args:
            session: The game session
            additional_context: Optional additional context to include

        Returns:
            Dict: Context information for the current state
        """
        # Base context common to all states
        context = {
            "character": session.character.get_summary(),
            "current_state": session.current_state.name,
            "recent_history": session.get_recent_history(),
        }

        # State-specific context
        if session.current_state == GameState.EXPLORATION:
            if session.world.current_location:
                context["location"] = session.world.get_location_description(
                    session.world.current_location
                )
                context["discovered_locations"] = list(
                    session.world.discovered_locations
                )

        elif session.current_state == GameState.COMBAT:
            # Combat-specific context would be added here
            # This would typically include enemies, battlefield state, turn order, etc.
            context["combat_state"] = "Combat context would be populated here"

        elif session.current_state == GameState.DIALOGUE:
            # Dialogue-specific context would be added here
            # This would typically include NPC info, conversation history, etc.
            context["dialogue_state"] = "Dialogue context would be populated here"

        elif session.current_state == GameState.SKILL_CHECK:
            # Skill check context would be added here
            context["skill_check_state"] = "Skill check context would be populated here"

        elif session.current_state == GameState.INVENTORY:
            context["inventory"] = session.inventory.get_summary()

        elif session.current_state == GameState.CHARACTER_SHEET:
            context["character_details"] = session.character.dict()

        # Add any additional context
        if additional_context:
            context.update(additional_context)

        return context

    @classmethod
    def get_ui_state(cls, session: Session) -> Dict[str, Any]:
        """
        Get the UI state information for the current game state.

        Args:
            session: The game session

        Returns:
            Dict: UI state information
        """
        # Basic UI state common to all states
        ui_state = {
            "current_state": session.current_state.name,
            "allowed_actions": cls.get_valid_actions(session.current_state),
            "allowed_transitions": [
                state.name for state in cls.get_valid_transitions(session.current_state)
            ],
        }

        # State-specific UI elements
        if session.current_state == GameState.EXPLORATION:
            if session.world.current_location:
                location = session.world.locations.get(session.world.current_location)
                ui_state["location_name"] = location.name if location else "Unknown"
                ui_state["exits"] = (
                    [exit.destination_id for exit in location.exits] if location else []
                )
                ui_state["region"] = session.world.current_region

        elif session.current_state == GameState.COMBAT:
            # Combat-specific UI elements
            ui_state["combat_ui"] = "Combat UI elements would be defined here"

        elif session.current_state == GameState.DIALOGUE:
            # Dialogue-specific UI elements
            ui_state["dialogue_ui"] = "Dialogue UI elements would be defined here"

        # Add character stats summary for all states
        ui_state["character_summary"] = {
            "name": session.character.name,
            "class": session.character.class_type,
            "level": session.character.level,
            "health": f"{session.character.health}/{session.character.max_health}",
            "mana": f"{session.character.mana}/{session.character.max_mana}",
        }

        return ui_state


# Example of registering action handlers (would be done elsewhere in the application)
# This is just to show how handlers would be registered

# async def handle_exploration_move(session: Session, action_data: Dict[str, Any]) -> Dict[str, Any]:
#     """Handle movement in exploration state."""
#     destination = action_data.get("destination")
#     if not destination:
#         return {"success": False, "error": "No destination specified"}

#     result = session.world.change_location(destination)
#     if not result.get("success", False):
#         return result

#     return {
#         "success": True,
#         "description": f"Moved to {destination}",
#         "location": session.world.get_location_description(destination),
#         "outcome": "Successfully changed location"
#     }

# Example of how to register this handler:
# StateManager.register_action_handler(GameState.EXPLORATION, "move", handle_exploration_move)
