# app/models/character.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4


class Ability(BaseModel):
    """Model representing a character ability."""

    id: str
    name: str
    description: str
    cooldown: int = 0
    current_cooldown: int = 0


class Trait(BaseModel):
    """Model representing a character trait."""

    id: str
    name: str
    description: str
    effects: Dict[str, int] = {}


class EquipmentSlots(BaseModel):
    """Model representing character equipment slots."""

    head: Optional[str] = None
    chest: Optional[str] = None
    hands: Optional[str] = None
    legs: Optional[str] = None
    feet: Optional[str] = None
    weapon_1: Optional[str] = None
    weapon_2: Optional[str] = None
    accessory_1: Optional[str] = None
    accessory_2: Optional[str] = None


class CompanionCharacter(BaseModel):
    """Model representing a companion character."""

    id: str
    name: str
    description: str
    health: int
    max_health: int
    abilities: List[Ability] = []
    traits: List[Trait] = []


class Character(BaseModel):
    """Model representing the player character."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    class_type: str
    origin: str
    level: int = 1
    experience: int = 0
    health: int
    max_health: int
    mana: int
    max_mana: int
    skills: Dict[str, int] = {}
    abilities: List[Ability] = []
    traits: List[Trait] = []
    equipment: EquipmentSlots = Field(default_factory=EquipmentSlots)
    companions: List[CompanionCharacter] = []
    created_at: datetime = Field(default_factory=datetime.now)

    def get_summary(self) -> Dict:
        """Return a summary of the character for LLM context."""
        return {
            "name": self.name,
            "class": self.class_type,
            "origin": self.origin,
            "level": self.level,
            "health": f"{self.health}/{self.max_health}",
            "mana": f"{self.mana}/{self.max_mana}",
            "key_abilities": [
                a.name for a in self.abilities[:3]
            ],  # Just the first 3 for brevity
            "key_traits": [t.name for t in self.traits[:3]],
        }
