# models/player.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Set
from enum import Enum

class StatusEffect(BaseModel):
    """Model for status effects on the player"""
    id: str
    name: str
    description: str
    duration: int  # Number of turns remaining
    effect_type: str
    value: float
    
class Item(BaseModel):
    """Model for an item in the player's inventory"""
    id: str
    name: str
    description: str
    item_type: str  # weapon, armor, consumable, key, etc.
    properties: Optional[Dict[str, str]] = None
    count: int = 1
    
class Ability(BaseModel):
    """Model for a character ability"""
    id: str
    name: str
    description: str
    mana_cost: int
    cooldown: int = 0
    current_cooldown: int = 0
    effect: Dict[str, str]
    
class Quest(BaseModel):
    """Model for a quest in the player's journal"""
    id: str
    name: str
    description: str
    status: str = "active"  # active, completed, failed
    objectives: List[Dict[str, str]]
    rewards: Optional[Dict[str, str]] = None
    
class PlayerData(BaseModel):
    """Model containing all player character data"""
    name: str
    character_class: str
    origin: str
    level: int = 1
    experience: int = 0
    health: int
    max_health: int
    mana: int
    max_mana: int
    skills: Dict[str, int]  # Skill name -> skill level
    abilities: List[Ability] = []
    active_abilities: List[str] = []  # IDs of equipped abilities (max 4)
    inventory: List[Item] = []
    max_inventory: int = 20
    status_effects: List[StatusEffect] = []
    quests: List[Quest] = []
    
    @classmethod
    def create(cls, name: str, character_class: str, origin: str) -> "PlayerData":
        """Factory method to create a new player with default values based on class/origin"""
        from config.constants import CHARACTER_CLASSES, CHARACTER_ORIGINS, SKILLS
        
        class_data = CHARACTER_CLASSES.get(character_class.lower(), CHARACTER_CLASSES["psychic"])
        
        # Set base health and mana from class
        max_health = class_data["base_health"]
        max_mana = class_data["base_mana"]
        
        # Set up default skills
        skills = {skill: 1 for skill in SKILLS.keys()}
        
        # Add class skill bonuses
        for skill in class_data["starting_skills"]:
            skills[skill] = 2
        
        return cls(
            name=name,
            character_class=character_class,
            origin=origin,
            health=max_health,
            max_health=max_health,
            mana=max_mana,
            max_mana=max_mana,
            skills=skills
        )
    
    def add_item(self, item: Item) -> bool:
        """Add an item to the player's inventory"""
        # Check if inventory is full
        if len(self.inventory) >= self.max_inventory:
            return False
            
        # Check if item already exists (stackable)
        for existing_item in self.inventory:
            if existing_item.id == item.id and existing_item.item_type != "quest":
                existing_item.count += item.count
                return True
                
        # Otherwise add as new item
        self.inventory.append(item)
        return True
    
    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """Remove an item from inventory"""
        for i, item in enumerate(self.inventory):
            if item.id == item_id:
                if item.count > count:
                    item.count -= count
                    return True
                elif item.count == count:
                    self.inventory.pop(i)
                    return True
                else:
                    return False
        return False
    
    def has_item(self, item_id: str) -> bool:
        """Check if player has a specific item"""
        return any(item.id == item_id for item in self.inventory)
    
    def add_status_effect(self, effect: StatusEffect) -> None:
        """Add a status effect to the player"""
        # Replace if exists, otherwise add
        for i, existing in enumerate(self.status_effects):
            if existing.id == effect.id:
                self.status_effects[i] = effect
                return
        self.status_effects.append(effect)
    
    def remove_status_effect(self, effect_id: str) -> bool:
        """Remove a status effect from the player"""
        initial_length = len(self.status_effects)
        self.status_effects = [e for e in self.status_effects if e.id != effect_id]
        return len(self.status_effects) < initial_length
    
    def update_status_effects(self) -> List[str]:
        """Update duration on status effects and remove expired ones.
        Returns list of expired effect names."""
        expired = []
        remaining = []
        
        for effect in self.status_effects:
            effect.duration -= 1
            if effect.duration <= 0:
                expired.append(effect.name)
            else:
                remaining.append(effect)
                
        self.status_effects = remaining
        return expired