# models/state.py
from enum import Enum, auto
from typing import Dict, List, Set, Optional
from pydantic import BaseModel

class GameState(str, Enum):
    """Enum representing the current state of the game"""
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    SKILL_CHECK = "skill_check"
    INVENTORY = "inventory"
    CHARACTER_SHEET = "character_sheet"
    MENU = "menu"

class StateTransition(BaseModel):
    """Model for state transitions in the game's state machine"""
    current_state: GameState
    next_state: GameState
    conditions: Optional[Dict[str, str]] = None
    allowed: bool = True

class StateMachine(BaseModel):
    """Manages valid state transitions and actions"""
    transitions: Dict[GameState, Set[GameState]]
    allowed_actions: Dict[GameState, List[str]]
    
    @classmethod
    def default(cls) -> "StateMachine":
        """Create a default state machine with standard transitions"""
        return cls(
            transitions={
                GameState.EXPLORATION: {
                    GameState.COMBAT, 
                    GameState.DIALOGUE, 
                    GameState.SKILL_CHECK, 
                    GameState.INVENTORY, 
                    GameState.CHARACTER_SHEET, 
                    GameState.MENU
                },
                GameState.COMBAT: {
                    GameState.EXPLORATION, 
                    GameState.INVENTORY, 
                    GameState.MENU
                },
                GameState.DIALOGUE: {
                    GameState.EXPLORATION, 
                    GameState.COMBAT, 
                    GameState.SKILL_CHECK, 
                    GameState.MENU
                },
                GameState.SKILL_CHECK: {
                    GameState.EXPLORATION, 
                    GameState.DIALOGUE, 
                    GameState.COMBAT, 
                    GameState.MENU
                },
                GameState.INVENTORY: {
                    GameState.EXPLORATION, 
                    GameState.COMBAT, 
                    GameState.MENU
                },
                GameState.CHARACTER_SHEET: {
                    GameState.EXPLORATION, 
                    GameState.INVENTORY, 
                    GameState.MENU
                },
                GameState.MENU: {
                    GameState.EXPLORATION, 
                    GameState.COMBAT, 
                    GameState.DIALOGUE, 
                    GameState.SKILL_CHECK, 
                    GameState.INVENTORY, 
                    GameState.CHARACTER_SHEET
                }
            },
            allowed_actions={
                GameState.EXPLORATION: ["move", "examine", "interact", "talk", "use_item"],
                GameState.COMBAT: ["attack", "use_ability", "use_item", "defend", "flee"],
                GameState.DIALOGUE: ["respond", "question", "leave", "use_item"],
                GameState.SKILL_CHECK: ["attempt", "use_item", "abort"],
                GameState.INVENTORY: ["examine_item", "use_item", "drop_item", "combine_items"],
                GameState.CHARACTER_SHEET: ["view_stats", "level_up", "assign_points"],
                GameState.MENU: ["save", "load", "settings", "exit"]
            }
        )
    
    def can_transition(self, from_state: GameState, to_state: GameState) -> bool:
        """Check if a transition from one state to another is allowed"""
        return to_state in self.transitions.get(from_state, set())
    
    def is_action_allowed(self, state: GameState, action: str) -> bool:
        """Check if an action is allowed in the current state"""
        return action in self.allowed_actions.get(state, [])
    
    def get_allowed_actions(self, state: GameState) -> List[str]:
        """Get all allowed actions for a given state"""
        return self.allowed_actions.get(state, [])
    
    def get_allowed_transitions(self, state: GameState) -> Set[GameState]:
        """Get all allowed transitions from a given state"""
        return self.transitions.get(state, set())