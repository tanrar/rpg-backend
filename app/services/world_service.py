# app/services/world_service.py
from typing import Dict, List, Set, Optional, Any
import logging
from pydantic import BaseModel, Field

from app.data.locations import LOCATIONS, REGIONS, THEMES, NPCS, OBJECTS
from app.models.world import Location, Region, ThemeSettings, Exit, WorldState

logger = logging.getLogger(__name__)

class WorldService:
    """
    Service for managing world-related data and operations.
    
    This service is responsible for:
    1. Loading location data
    2. Creating world state for new sessions
    3. Retrieving location information
    4. Managing location transitions
    """
    
    @staticmethod
    def initialize_world_state(starting_location_id: str = "starting_camp") -> WorldState:
        """
        Create a new world state with the default data.
        
        Args:
            starting_location_id: The ID of the starting location
            
        Returns:
            WorldState: A new world state object
        """
        # Convert data to appropriate models
        regions = {
            region_id: Region(**region_data)
            for region_id, region_data in REGIONS.items()
        }
        
        locations = {}
        for loc_id, loc_data in LOCATIONS.items():
            # Convert exit data to Exit objects
            exits = [Exit(**exit_data) for exit_data in loc_data.get("exits", [])]
            
            # Create location object
            location = Location(
                id=loc_data["id"],
                name=loc_data["name"],
                description=loc_data["description"],
                region=loc_data["region"],
                exits=exits,
                npcs=loc_data.get("npcs", []),
                objects=loc_data.get("objects", []),
                visited=False,
                visit_count=0,
                image=loc_data.get("image", None),
                theme=loc_data.get("theme", None)
            )
            
            locations[loc_id] = location
        
        # Get the region of the starting location
        starting_region = locations[starting_location_id].region if starting_location_id in locations else None
        
        # Get theme settings for the starting region
        theme = None
        if starting_region and starting_region in REGIONS:
            theme_id = REGIONS[starting_region].get("theme")
            if theme_id and theme_id in THEMES:
                theme_data = THEMES[theme_id]
                theme = ThemeSettings(
                    id=theme_id,
                    name=theme_id.replace("_", " ").title(),
                    primary_color=theme_data["primary_color"],
                    secondary_color=theme_data["secondary_color"],
                    text_color=theme_data["text_color"],
                    accent_color=theme_data["accent_color"],
                    font=theme_data.get("font", "default"),
                    ambient_sound=theme_data.get("ambient_sound", None)
                )
        
        # Create and return world state
        return WorldState(
            regions=regions,
            current_region=starting_region,
            locations=locations,
            current_location=starting_location_id,
            discovered_locations={starting_location_id},
            npcs=NPCS,
            faction_standings={},
            global_flags={},
            time_passed=0,
            theme=theme
        )
    
    @staticmethod
    def get_image_for_location(location_id: str) -> Optional[Dict[str, str]]:
        """
        Get image information for a location.
        
        Args:
            location_id: The ID of the location
            
        Returns:
            Optional[Dict]: Image information or None if not available
        """
        if location_id in LOCATIONS:
            loc_data = LOCATIONS[location_id]
            
            if "image" in loc_data:
                return {
                    "id": loc_data["image"],
                    "prompt": loc_data.get("image_prompt", f"A scene of {loc_data['name']}")
                }
        
        return None
    
    @staticmethod
    def get_theme_for_location(location_id: str) -> Optional[ThemeSettings]:
        """
        Get theme settings for a location based on its region.
        
        Args:
            location_id: The ID of the location
            
        Returns:
            Optional[ThemeSettings]: Theme settings or None if not available
        """
        if location_id in LOCATIONS:
            region_id = LOCATIONS[location_id].get("region")
            
            if region_id and region_id in REGIONS:
                theme_id = REGIONS[region_id].get("theme")
                
                if theme_id and theme_id in THEMES:
                    theme_data = THEMES[theme_id]
                    return ThemeSettings(
                        id=theme_id,
                        name=theme_id.replace("_", " ").title(),
                        primary_color=theme_data["primary_color"],
                        secondary_color=theme_data["secondary_color"],
                        text_color=theme_data["text_color"],
                        accent_color=theme_data["accent_color"],
                        font=theme_data.get("font", "default"),
                        ambient_sound=theme_data.get("ambient_sound", None)
                    )
        
        return None
    
    @staticmethod
    def get_npc_details(npc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for an NPC.
        
        Args:
            npc_id: The ID of the NPC
            
        Returns:
            Optional[Dict]: NPC details or None if not found
        """
        return NPCS.get(npc_id)
    
    @staticmethod
    def get_object_details(object_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a game object.
        
        Args:
            object_id: The ID of the object
            
        Returns:
            Optional[Dict]: Object details or None if not found
        """
        return OBJECTS.get(object_id)
    
    @staticmethod
    def validate_movement(current_location_id: str, destination_id: str) -> bool:
        """
        Check if movement from current location to destination is valid.
        
        Args:
            current_location_id: The ID of the current location
            destination_id: The ID of the destination
            
        Returns:
            bool: True if movement is valid, False otherwise
        """
        if current_location_id not in LOCATIONS:
            return False
            
        location = LOCATIONS[current_location_id]
        
        # Check if destination is a valid exit
        for exit_data in location.get("exits", []):
            if exit_data.get("destination_id") == destination_id:
                return True
                
        return False