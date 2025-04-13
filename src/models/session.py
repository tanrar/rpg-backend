# models/session.py
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Set

from models.player import PlayerData
from models.state import GameState, StateMachine
from models.world import WorldState, Location, NPC

class LLMContext(BaseModel):
    """Stores context for LLM responses to maintain consistency"""
    narrative_history: List[Dict[str, str]] = []  # Past narrative descriptions
    action_history: List[Dict[str, str]] = []  # Past player actions
    key_events: List[str] = []  # Important narrative events
    location_context: Optional[Dict[str, Any]] = None  # Current location details
    
    def add_narrative(self, text: str) -> None:
        """Add a narrative description to history"""
        self.narrative_history.append({
            "timestamp": datetime.now().isoformat(),
            "text": text
        })
        # Keep only the most recent entries
        if len(self.narrative_history) > 10:  # Configurable
            self.narrative_history.pop(0)
    
    def add_action(self, action: str, result: str) -> None:
        """Add a player action and result to history"""
        self.action_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "result": result
        })
        # Keep only the most recent entries
        if len(self.action_history) > 10:  # Configurable
            self.action_history.pop(0)
    
    def add_key_event(self, event: str) -> None:
        """Add an important event to key_events"""
        self.key_events.append(event)
    
    def update_location(self, location: Dict[str, Any]) -> None:
        """Update current location context"""
        self.location_context = location

class CombatState(BaseModel):
    """Model for tracking combat state"""
    active: bool = False
    enemies: List[Dict[str, Any]] = []
    initiative_order: List[str] = []
    current_turn: str = ""
    round: int = 0
    combat_log: List[str] = []
    ambush_state: Optional[str] = None  # player_surprised, enemies_surprised, none
    
    def add_to_log(self, entry: str) -> None:
        """Add an entry to the combat log"""
        self.combat_log.append(entry)
        if len(self.combat_log) > 20:  # Keep log manageable
            self.combat_log.pop(0)
    
    def next_turn(self) -> str:
        """Advance to the next turn and return whose turn it is"""
        if not self.initiative_order:
            return ""
            
        current_index = self.initiative_order.index(self.current_turn)
        next_index = (current_index + 1) % len(self.initiative_order)
        
        # If we loop back to the first actor, increment the round
        if next_index == 0:
            self.round += 1
            
        self.current_turn = self.initiative_order[next_index]
        return self.current_turn

class DialogueState(BaseModel):
    """Model for tracking dialogue state"""
    active: bool = False
    npc_id: Optional[str] = None
    conversation_history: List[Dict[str, str]] = []
    current_options: List[Dict[str, str]] = []
    
    def add_exchange(self, speaker: str, text: str) -> None:
        """Add a dialogue exchange to the conversation history"""
        self.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })

class SkillCheckState(BaseModel):
    """Model for tracking skill check state"""
    active: bool = False
    skill: Optional[str] = None
    difficulty: int = 5
    modifier: int = 0
    success_outcome: Optional[Dict[str, Any]] = None
    failure_outcome: Optional[Dict[str, Any]] = None

class GameSession(BaseModel):
    """Model containing all data for a game session"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    state: GameState = GameState.EXPLORATION
    player: PlayerData
    world_state: WorldState
    current_location: str
    combat_state: CombatState = Field(default_factory=CombatState)
    dialogue_state: DialogueState = Field(default_factory=DialogueState)
    skill_check_state: SkillCheckState = Field(default_factory=SkillCheckState)
    llm_context: LLMContext = Field(default_factory=LLMContext)
    state_machine: StateMachine = Field(default_factory=StateMachine.default)
    
    def update_timestamp(self) -> None:
        """Update the session's last updated timestamp"""
        self.updated_at = datetime.now()
    
    def can_transition_to(self, new_state: GameState) -> bool:
        """Check if the session can transition to a new state"""
        return self.state_machine.can_transition(self.state, new_state)
    
    def transition_to(self, new_state: GameState) -> bool:
        """Attempt to transition to a new state"""
        if self.can_transition_to(new_state):
            self.state = new_state
            self.update_timestamp()
            return True
        return False
    
    def is_action_allowed(self, action: str) -> bool:
        """Check if an action is allowed in the current state"""
        return self.state_machine.is_action_allowed(self.state, action)
    
    def get_allowed_actions(self) -> List[str]:
        """Get all allowed actions for the current state"""
        return self.state_machine.get_allowed_actions(self.state)
    
    def get_allowed_transitions(self) -> Set[GameState]:
        """Get all allowed state transitions from the current state"""
        return self.state_machine.get_allowed_transitions(self.state)
    
    @classmethod
    def create(cls, player_name: str, character_class: str, origin: str) -> "GameSession":
        """Factory method to create a new game session"""
        from config.constants import STARTING_LOCATIONS
        from models.world import WorldState
        
        player = PlayerData.create(player_name, character_class, origin)
        world_state = WorldState.create()
        starting_location = STARTING_LOCATIONS[0]
        
        return cls(
            player=player,
            world_state=world_state,
            current_location=starting_location
        )