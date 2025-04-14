# app/data/locations.py
from typing import Dict, List, Optional

# Location themes with color schemes
THEMES = {
    "wasteland": {
        "primary_color": "#8e7d5c", 
        "secondary_color": "#5a4d3a",
        "text_color": "#f0e6d2",
        "accent_color": "#b38b59",
        "font": "Montserrat",
        "ambient_sound": "wind_desert.mp3"
    },
    "ruins": {
        "primary_color": "#526b7a",
        "secondary_color": "#2e404c",
        "text_color": "#e0e7ed",
        "accent_color": "#7097b3",
        "font": "Montserrat",
        "ambient_sound": "ruins_ambience.mp3"
    },
    "ancient_facility": {
        "primary_color": "#405c73",
        "secondary_color": "#233240", 
        "text_color": "#d8e6f2",
        "accent_color": "#5992c3",
        "font": "Montserrat",
        "ambient_sound": "facility_hum.mp3"
    },
    "settlement": {
        "primary_color": "#6d5c4d",
        "secondary_color": "#40352c",
        "text_color": "#f2e8df",
        "accent_color": "#a67c52",
        "font": "Montserrat",
        "ambient_sound": "settlement_chatter.mp3"
    }
}

# Region definitions
REGIONS = {
    "starting_region": {
        "id": "starting_region",
        "name": "The Wastes",
        "description": "A barren wasteland stretching as far as the eye can see. Dust storms occasionally sweep through, obscuring vision and making travel hazardous.",
        "theme": "wasteland",
        "danger_level": 1
    },
    "ancient_ruins": {
        "id": "ancient_ruins",
        "name": "Ancient Ruins",
        "description": "The crumbling remains of a once-great city. Structures of metal and stone jut from the sand, their purpose long forgotten.",
        "theme": "ruins",
        "danger_level": 2
    },
    "forgotten_facility": {
        "id": "forgotten_facility",
        "name": "Forgotten Facility",
        "description": "A partially buried complex of unknown origin. Strange technology still functions within its walls.",
        "theme": "ancient_facility",
        "danger_level": 3
    },
    "survivors_enclave": {
        "id": "survivors_enclave",
        "name": "Survivors' Enclave",
        "description": "A small settlement built from salvaged materials where hardy wastelanders have banded together for mutual protection.",
        "theme": "settlement",
        "danger_level": 1
    }
}

# Location definitions
LOCATIONS = {
    "starting_camp": {
        "id": "starting_camp",
        "name": "Survivors' Camp",
        "description": "A small encampment built from scavenged materials. A few survivors have made this their temporary home.",
        "region": "starting_region",
        "exits": [
            {
                "destination_id": "ruined_road",
                "description": "A path leading to a ruined road stretches to the east."
            }
        ],
        "npcs": ["camp_leader"],
        "objects": ["supply_cache", "campfire"],
        "image": "survivors_camp",
        "image_prompt": "A small camp in a barren wasteland with makeshift tents and a central campfire, post-apocalyptic setting, harsh lighting"
    },
    "ruined_road": {
        "id": "ruined_road",
        "name": "Ruined Road",
        "description": "An ancient asphalt road, cracked and weathered by time. Rusted vehicles line the sides.",
        "region": "starting_region",
        "exits": [
            {
                "destination_id": "starting_camp",
                "description": "The survivors' camp is visible to the west."
            },
            {
                "destination_id": "abandoned_facility",
                "description": "The road continues east toward what appears to be an abandoned facility."
            },
            {
                "destination_id": "crossroads",
                "description": "The road branches to the north at a weathered crossroads."
            }
        ],
        "objects": ["rusted_vehicle", "road_sign"],
        "image": "ruined_road",
        "image_prompt": "A cracked and weathered highway with rusted abandoned vehicles, post-apocalyptic desert landscape, no people, harsh sunlight"
    },
    "abandoned_facility": {
        "id": "abandoned_facility",
        "name": "Abandoned Facility",
        "description": "A concrete structure protruding from the sand, its purpose unclear. Heavy metal doors hang partially open.",
        "region": "forgotten_facility",
        "exits": [
            {
                "destination_id": "ruined_road",
                "description": "The ruined road leads back west."
            },
            {
                "destination_id": "facility_entrance",
                "description": "A dark entrance leads into the facility."
            }
        ],
        "objects": ["control_panel", "warning_sign", "debris"],
        "image": "abandoned_facility",
        "image_prompt": "Exterior of a weathered concrete bunker or facility partially buried in sand, post-apocalyptic, harsh lighting, imposing entrance"
    },
    "facility_entrance": {
        "id": "facility_entrance",
        "name": "Facility Entrance Hall",
        "description": "A dimly lit entrance hall. Dust covers everything, but some lights still flicker from emergency power.",
        "region": "forgotten_facility",
        "exits": [
            {
                "destination_id": "abandoned_facility",
                "description": "Daylight filters through the entrance behind you."
            },
            {
                "destination_id": "facility_corridor",
                "description": "A dark corridor extends deeper into the facility."
            }
        ],
        "objects": ["security_terminal", "fallen_ceiling", "locker"],
        "image": "facility_entrance",
        "image_prompt": "Interior of a dark, dusty entrance hall in an abandoned facility with flickering emergency lights, post-apocalyptic, debris scattered"
    },
    "crossroads": {
        "id": "crossroads",
        "name": "Desolate Crossroads",
        "description": "A junction where the road splits in multiple directions. An old, rusted sign post barely stands, the writing long since faded.",
        "region": "starting_region",
        "exits": [
            {
                "destination_id": "ruined_road",
                "description": "The main road continues south."
            },
            {
                "destination_id": "ancient_settlement",
                "description": "A path leads north toward what might be an old settlement."
            }
        ],
        "objects": ["signpost", "abandoned_cart"],
        "image": "crossroads",
        "image_prompt": "A desolate crossroads in a wasteland with a weathered signpost, cracked roads extending in different directions, barren landscape"
    },
    "ancient_settlement": {
        "id": "ancient_settlement",
        "name": "Ancient Settlement",
        "description": "The ruins of a small town, most buildings reduced to their foundations. A few structures remain partially intact.",
        "region": "ancient_ruins",
        "exits": [
            {
                "destination_id": "crossroads",
                "description": "The path back to the crossroads lies to the south."
            },
            {
                "destination_id": "settlement_center",
                "description": "What might have been the town center is visible ahead."
            }
        ],
        "objects": ["collapsed_building", "old_fountain"],
        "image": "ancient_settlement",
        "image_prompt": "Ruins of a small town with mostly collapsed buildings, a few walls still standing, post-apocalyptic, arid environment"
    },
    "settlement_center": {
        "id": "settlement_center",
        "name": "Settlement Center",
        "description": "What once must have been the central plaza of the settlement. A large, dried fountain sits in the middle, surrounded by the remnants of shops and apartments.",
        "region": "ancient_ruins",
        "exits": [
            {
                "destination_id": "ancient_settlement",
                "description": "The path back to the settlement entrance is behind you."
            }
        ],
        "npcs": ["wandering_scavenger"],
        "objects": ["central_fountain", "buried_cache"],
        "image": "settlement_center",
        "image_prompt": "Central plaza of a ruined town with a dried stone fountain in the center, destroyed buildings surrounding it, post-apocalyptic, desolate"
    }
}

# NPC definitions
NPCS = {
    "camp_leader": {
        "id": "camp_leader",
        "name": "Soren",
        "description": "A weathered survivor with a stern expression but kind eyes. Scars crisscross his face, telling of past hardships.",
        "disposition": "friendly",
        "knowledge": ["survivors_camp", "ruined_road", "basic_survival"]
    },
    "wandering_scavenger": {
        "id": "wandering_scavenger",
        "name": "Mira",
        "description": "A cautious woman dressed in mismatched armor pieces, constantly scanning her surroundings. A collection of found items hangs from her belt.",
        "disposition": "neutral",
        "knowledge": ["ancient_ruins", "valuable_salvage", "hidden_dangers"]
    }
}

# Game objects definitions
OBJECTS = {
    "supply_cache": {
        "id": "supply_cache",
        "name": "Supply Cache",
        "description": "A metal container holding the camp's communal supplies. Contains basic medical items and some food rations.",
        "interactions": ["examine", "open"]
    },
    "campfire": {
        "id": "campfire",
        "name": "Campfire",
        "description": "A small fire burning in a ring of stones. It provides warmth and light for the camp.",
        "interactions": ["examine", "sit_by"]
    },
    "rusted_vehicle": {
        "id": "rusted_vehicle",
        "name": "Rusted Vehicle",
        "description": "The corroded shell of what was once a car. Most useful parts have already been scavenged.",
        "interactions": ["examine", "search"]
    },
    "road_sign": {
        "id": "road_sign",
        "name": "Road Sign",
        "description": "A faded metal sign, barely legible. It points to destinations that may no longer exist.",
        "interactions": ["examine", "read"]
    },
    "control_panel": {
        "id": "control_panel",
        "name": "Control Panel",
        "description": "A panel with buttons and switches, some still operational. Its purpose isn't immediately clear.",
        "interactions": ["examine", "activate"]
    },
    "warning_sign": {
        "id": "warning_sign",
        "name": "Warning Sign",
        "description": "A yellow metal sign with faded text warning about restricted access and potential hazards.",
        "interactions": ["examine", "read"]
    }
}