# app/models/game_state.py
from enum import Enum, auto


class GameState(Enum):
    """Enum representing different game states."""

    EXPLORATION = auto()
    COMBAT = auto()
    DIALOGUE = auto()
    SKILL_CHECK = auto()
    INVENTORY = auto()
    CHARACTER_SHEET = auto()
    MENU = auto()
