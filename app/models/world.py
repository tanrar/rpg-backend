# app/models/world.py (update)
from pydantic import BaseModel, Field
from typing import Dict, List, Set, Optional
from datetime import datetime
from uuid import UUID, uuid4

class Exit(BaseModel):
    """Model representing an exit from a location."""
    destination_id: str
    description: str
    is_locked: bool = False
    key_item_id: Optional[str] = None
    
class Location(BaseModel):
    """Model representing a location in the game world."""
    id: str
    name: str
    description: str
    region: str
    exits: List[Exit] = []
    npcs: List[str] = []
    objects: List[str] = []
    visited: bool = False
    visit_count: int = 0
    image: Optional[str] = None
    theme: Optional[str] = None

class Region(BaseModel):
    """Model representing a region in the game world."""
    id: str
    name: str
    description: str
    theme: str
    danger_level: int = 1

class ThemeSettings(BaseModel):
    """Model representing visual theme settings."""
    id: str
    name: str
    primary_color: str
    secondary_color: str
    text_color: str
    accent_color: str
    font: str = "default"
    ambient_sound: Optional[str] = None

class WorldState(BaseModel):
    """Model representing the state of the game world."""
    id: UUID = Field(default_factory=uuid4)
    regions: Dict[str, Region] = {}
    current_region: Optional[str] = None
    locations: Dict[str, Location] = {}
    current_location: Optional[str] = None
    discovered_locations: Set[str] = Field(default_factory=set)
    npcs: Dict[str, Dict] = {}  # Simplified NPC state tracking
    faction_standings: Dict[str, int] = {}  # -100 to 100
    global_flags: Dict[str, bool] = {}
    time_passed: int = 0  # In-game time units
    theme: Optional[ThemeSettings] = None
    
    def get_location_description(self, location_id: str) -> Optional[Dict]:
        """Get description data for a location."""
        if location_id not in self.locations:
            return None
            
        location = self.locations[location_id]
        return {
            "id": location.id,
            "name": location.name,
            "description": location.description,
            "region": location.region,
            "exits": [{"destination": exit.destination_id, "description": exit.description} 
                     for exit in location.exits if not exit.is_locked],
            "npcs_present": location.npcs,
            "objects": location.objects,
            "visited_before": location.visit_count > 0,
            "image": location.image
        }
    
    def change_location(self, location_id: str) -> Dict:
        """Change the current location."""
        if location_id not in self.locations:
            return {
                "success": False,
                "error": "Location not found"
            }
            
        previous_location = self.current_location
        self.current_location = location_id
        
        # Update location visit information
        location = self.locations[location_id]
        if not location.visited:
            location.visited = True
        location.visit_count += 1
        
        # Update the current region if needed
        self.current_region = location.region
        
        # Add to discovered locations
        self.discovered_locations.add(location_id)
        
        # Update theme based on the region
        for region_id, region in self.regions.items():
            if region_id == location.region:
                # Theme is updated elsewhere based on the region
                break
        
        return {
            "success": True,
            "previous_location": previous_location,
            "new_location": location_id,
            "description": location.description,
            "first_visit": location.visit_count == 1,
            "image": location.image
        }