# models/world.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime

class NPC(BaseModel):
    """Model for an NPC in the game world"""
    id: str
    name: str
    description: str
    location: str
    dialogue_state: Dict[str, Any] = {}
    inventory: List[Dict[str, Any]] = []
    hostile: bool = False
    health: Optional[int] = None
    max_health: Optional[int] = None
    faction: Optional[str] = None
    
class Location(BaseModel):
    """Model for a location in the game world"""
    id: str
    name: str
    description: str
    image: Optional[str] = None
    visited: bool = False
    connections: List[str] = []  # IDs of connected locations
    npcs: List[str] = []  # IDs of NPCs in this location
    items: List[Dict[str, Any]] = []  # Items in this location
    interactive_objects: List[Dict[str, Any]] = []  # Objects that can be interacted with
    environment_effects: List[Dict[str, Any]] = []  # Environmental effects (e.g., damage over time)
    
class Faction(BaseModel):
    """Model for a faction in the game world"""
    id: str
    name: str
    description: str
    disposition: int = 0  # -5 to 5 scale, negative is hostile
    npcs: List[str] = []  # IDs of NPCs in this faction
    
class QuestState(BaseModel):
    """Model for tracking the state of a quest in the world"""
    id: str
    name: str
    status: str  # inactive, active, completed, failed
    objectives: Dict[str, str] = {}  # objective_id -> status
    world_effects: List[Dict[str, Any]] = []  # Effects on the world when completed
    
class WorldState(BaseModel):
    """Model containing the current state of the game world"""
    locations: Dict[str, Location] = {}
    npcs: Dict[str, NPC] = {}
    factions: Dict[str, Faction] = {}
    quests: Dict[str, QuestState] = {}
    global_variables: Dict[str, Any] = {}
    time_elapsed: float = 0  # Game time elapsed in hours
    
    @classmethod
    def create(cls) -> "WorldState":
        """Factory method to create initial world state"""
        from config.constants import GAME_AREAS
        
        # Initialize with frozen cathedral locations
        locations = {}
        
        # Create the Frozen Cathedral entrance
        locations["frozen_cathedral_entrance"] = Location(
            id="frozen_cathedral_entrance",
            name="The Frozen Cathedral - Entrance",
            description="A massive doorway carved into the side of a glacier leads to an ancient structure. Frost-laden winds howl around you, but the air grows still as you approach the entrance. Faint blue light emanates from within, and strange symbols are etched into the ice around the doorframe.",
            connections=["frozen_cathedral_main_hall"],
            interactive_objects=[
                {
                    "id": "entrance_symbols",
                    "name": "Ancient Symbols",
                    "description": "Strange glyphs carved into the ice, glowing with a faint blue energy.",
                    "interaction_type": "examine",
                }
            ]
        )
        
        # Create the main hall
        locations["frozen_cathedral_main_hall"] = Location(
            id="frozen_cathedral_main_hall",
            name="The Frozen Cathedral - Main Hall",
            description="The massive hall stretches before you, its ceiling lost in shadows. Fractured ice columns rise like silent sentinels, reflecting the pale blue light that filters through stained glass windows. A soft hum emanates from a raised dais at the far end, where a peculiar beacon pulses with energy. The air feels charged, as if waiting for something to happen.",
            connections=["frozen_cathedral_entrance", "frozen_cathedral_altar", "frozen_cathedral_eastern_corridor", "frozen_cathedral_western_passage"],
            interactive_objects=[
                {
                    "id": "frozen_beacon",
                    "name": "Pulsing Beacon",
                    "description": "A crystalline structure atop a raised dais, pulsing with ethereal blue energy.",
                    "interaction_type": "activate",
                    "requires_item": "echo_key",
                }
            ]
        )
        
        # Add altar chamber
        locations["frozen_cathedral_altar"] = Location(
            id="frozen_cathedral_altar",
            name="The Frozen Cathedral - Altar Chamber",
            description="A circular chamber dominated by a massive altar of black stone. Unlike the rest of the cathedral, this area is devoid of ice, and the stone floor radiates a subtle warmth. Blue flames dance across the altar's surface without consuming it. The walls are covered in detailed murals depicting figures channeling energy into beacons similar to the one in the main hall.",
            connections=["frozen_cathedral_main_hall"],
            items=[
                {
                    "id": "echo_key",
                    "name": "Echo Key",
                    "description": "A translucent crystalline key that hums with the same frequency as the beacon.",
                    "item_type": "key",
                }
            ],
            interactive_objects=[
                {
                    "id": "altar_flames",
                    "name": "Blue Flames",
                    "description": "Ethereal flames that give off no heat, dancing across the surface of the altar.",
                    "interaction_type": "examine",
                }
            ]
        )
        
        # Add eastern corridor
        locations["frozen_cathedral_eastern_corridor"] = Location(
            id="frozen_cathedral_eastern_corridor",
            name="The Frozen Cathedral - Eastern Corridor",
            description="A long hallway lined with frozen statues. Each depicts a robed figure in various poses of reverence or contemplation. The ice here is thicker, and your footsteps echo loudly with each step. Strange whispers seem to follow you, though you can't pinpoint their source.",
            connections=["frozen_cathedral_main_hall"],
            npcs=["frost_guardian_1", "ice_imp_1", "ice_imp_2"]
        )
        
        # Add western passage
        locations["frozen_cathedral_western_passage"] = Location(
            id="frozen_cathedral_western_passage",
            name="The Frozen Cathedral - Western Passage",
            description="A twisting passage where the walls are formed of perfectly clear ice, revealing strange artifacts and relics embedded within. The temperature here is significantly colder than the main hall, and your breath comes out in visible puffs. The passage appears to lead deeper into the glacier, but the way is blocked by a wall of ice.",
            connections=["frozen_cathedral_main_hall"],
            interactive_objects=[
                {
                    "id": "ice_wall",
                    "name": "Wall of Ice",
                    "description": "A thick barrier of ice blocking further passage. It seems different from the surrounding walls, as if it was formed more recently.",
                    "interaction_type": "destroy",
                }
            ]
        )
        
        # Add hidden chamber (initially not connected)
        locations["frozen_cathedral_hidden_chamber"] = Location(
            id="frozen_cathedral_hidden_chamber",
            name="The Frozen Cathedral - Hidden Chamber",
            description="A small, hexagonal room revealed behind the melted ice wall. The walls here are made of metal rather than ice or stone, covered in complex circuitry that pulses with the same blue energy found throughout the cathedral. In the center of the room, a cylindrical container holds what appears to be a preserved human brain, floating in a luminescent fluid.",
            connections=["frozen_cathedral_western_passage"],
            interactive_objects=[
                {
                    "id": "brain_container",
                    "name": "Preserved Brain",
                    "description": "A human brain suspended in glowing blue fluid within a cylindrical metal and glass container. Delicate wires connect to various parts of the brain, and information streams across a small display on the container's base.",
                    "interaction_type": "examine",
                }
            ]
        )
        
        # Create NPCs
        npcs = {}
        
        # Frost Guardian
        npcs["frost_guardian_1"] = NPC(
            id="frost_guardian_1",
            name="Frost Guardian",
            description="A massive construct of animated ice and stone, formed into the shape of a knight with a blank, featureless face. It stands motionless until disturbed.",
            location="frozen_cathedral_eastern_corridor",
            hostile=True,
            health=60,
            max_health=60,
        )
        
        # Ice Imps
        npcs["ice_imp_1"] = NPC(
            id="ice_imp_1",
            name="Ice Imp",
            description="A small, mischievous creature formed of crystalline ice, with sharp claws and a manic grin.",
            location="frozen_cathedral_eastern_corridor",
            hostile=True,
            health=30,
            max_health=30,
        )
        
        npcs["ice_imp_2"] = NPC(
            id="ice_imp_2",
            name="Ice Imp",
            description="A small, mischievous creature formed of crystalline ice, with sharp claws and a manic grin.",
            location="frozen_cathedral_eastern_corridor",
            hostile=True,
            health=30,
            max_health=30,
        )
        
        # Frosted Archivist (will be added when player activates beacon)
        npcs["frosted_archivist"] = NPC(
            id="frosted_archivist",
            name="Frosted Archivist",
            description="A tall, slender figure composed of translucent ice with visible organs of blue energy pulsing within. Its voice reverberates as if coming from multiple sources at once, and it moves with unnatural grace.",
            location="frozen_cathedral_main_hall",
            hostile=False,
            dialogue_state={
                "introduced": False,
                "topics_discussed": [],
            }
        )
        
        # Create initial quests
        quests = {}
        quests["cathedral_mysteries"] = QuestState(
            id="cathedral_mysteries",
            name="Cathedral Mysteries",
            status="inactive",
            objectives={
                "find_echo_key": "inactive",
                "activate_beacon": "inactive",
                "investigate_whispers": "inactive",
                "find_hidden_chamber": "inactive",
            }
        )
        
        # Create initial factions
        factions = {}
        factions["cathedral_guardians"] = Faction(
            id="cathedral_guardians",
            name="Cathedral Guardians",
            description="The animated constructs and entities that protect the Frozen Cathedral.",
            disposition=-3,  # Initially hostile
            npcs=["frost_guardian_1", "ice_imp_1", "ice_imp_2"]
        )
        
        factions["archivists"] = Faction(
            id="archivists",
            name="The Archivists",
            description="Ancient keepers of knowledge who have transcended their physical forms.",
            disposition=0,  # Initially neutral
            npcs=["frosted_archivist"]
        )
        
        # Initialize global variables
        global_variables = {
            "beacon_activated": False,
            "ice_wall_melted": False,
            "archivist_summoned": False,
            "cathedral_explored": 0,  # Percentage explored
        }
        
        return cls(
            locations=locations,
            npcs=npcs,
            factions=factions,
            quests=quests,
            global_variables=global_variables
        )
    
    def update_npc_location(self, npc_id: str, new_location_id: str) -> bool:
        """Move an NPC to a new location"""
        if npc_id not in self.npcs or new_location_id not in self.locations:
            return False
            
        # Remove NPC from old location
        old_location_id = self.npcs[npc_id].location
        if old_location_id in self.locations:
            self.locations[old_location_id].npcs = [
                n for n in self.locations[old_location_id].npcs if n != npc_id
            ]
            
        # Add NPC to new location
        self.locations[new_location_id].npcs.append(npc_id)
        self.npcs[npc_id].location = new_location_id
        
        return True
    
    def add_connection(self, from_location: str, to_location: str) -> bool:
        """Add a connection between two locations"""
        if from_location not in self.locations or to_location not in self.locations:
            return False
            
        # Add bidirectional connection if not exists
        if to_location not in self.locations[from_location].connections:
            self.locations[from_location].connections.append(to_location)
            
        if from_location not in self.locations[to_location].connections:
            self.locations[to_location].connections.append(from_location)
            
        return True
    
    def remove_item_from_location(self, location_id: str, item_id: str) -> Optional[Dict]:
        """Remove an item from a location and return it"""
        if location_id not in self.locations:
            return None
            
        location = self.locations[location_id]
        for i, item in enumerate(location.items):
            if item["id"] == item_id:
                return location.items.pop(i)
                
        return None
    
    def activate_quest(self, quest_id: str) -> bool:
        """Activate a quest and its initial objectives"""
        if quest_id not in self.quests:
            return False
            
        quest = self.quests[quest_id]
        if quest.status != "inactive":
            return False
            
        quest.status = "active"
        
        # Activate first objective
        for obj_id in quest.objectives:
            if quest.objectives[obj_id] == "inactive":
                quest.objectives[obj_id] = "active"
                break
                
        return True
    
    def update_quest_objective(self, quest_id: str, objective_id: str, status: str) -> bool:
        """Update the status of a quest objective"""
        if quest_id not in self.quests:
            return False
            
        quest = self.quests[quest_id]
        if objective_id not in quest.objectives:
            return False
            
        quest.objectives[objective_id] = status
        
        # Check if all objectives are completed
        all_completed = all(
            s == "completed" for s in quest.objectives.values()
        )
        
        if all_completed:
            quest.status = "completed"
            
        return True