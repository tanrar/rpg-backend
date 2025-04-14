# app/models/inventory.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4


class ItemEffect(BaseModel):
    """Model representing an item effect."""

    type: str  # "status", "stat_boost", "damage", etc.
    target: str  # "self", "enemy", "ally", "area"
    value: int = 0
    duration: Optional[int] = None


class Item(BaseModel):
    """Model representing an item in the inventory."""

    id: str
    name: str
    description: str
    item_type: str  # "weapon", "armor", "consumable", "key", etc.
    rarity: str = "common"  # "common", "uncommon", "rare", "epic", "legendary"
    count: int = 1
    effects: List[ItemEffect] = []
    equippable: bool = False
    equipment_slot: Optional[str] = None  # If equippable, which slot
    value: int = 0  # Currency value


class Inventory(BaseModel):
    """Model representing the player's inventory."""

    id: UUID = Field(default_factory=uuid4)
    items: List[Item] = []
    capacity: int = 50
    currency: int = 0

    def add_item(self, item: Item) -> bool:
        """Add an item to the inventory."""
        # Check if inventory is full
        current_item_count = sum(i.count for i in self.items)
        if current_item_count + item.count > self.capacity:
            return False

        # Check if item already exists and is stackable
        for existing_item in self.items:
            if existing_item.id == item.id:
                existing_item.count += item.count
                return True

        # Otherwise add as new item
        self.items.append(item)
        return True

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """Remove an item from the inventory."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                if item.count > count:
                    item.count -= count
                    return True
                elif item.count == count:
                    self.items.pop(i)
                    return True
                else:
                    return False
        return False

    def get_summary(self) -> Dict:
        """Return a summary of the inventory for LLM context."""
        return {
            "items": [f"{item.name} ({item.count})" for item in self.items],
            "currency": self.currency,
            "capacity": f"{sum(i.count for i in self.items)}/{self.capacity}",
        }
