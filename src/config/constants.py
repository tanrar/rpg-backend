# config/constants.py
from enum import Enum, auto
from typing import Dict, List, Set

# Character classes
CHARACTER_CLASSES = {
    "courier": {
        "description": "Movement-based skirmisher/support",
        "base_health": 45,
        "base_mana": 25,
        "starting_skills": ["agility", "perception"],
    },
    "psychic": {
        "description": "Charge-based controller or nuker",
        "base_health": 40,
        "base_mana": 40,
        "starting_skills": ["willpower", "knowledge"],
    },
    "oathmarked": {
        "description": "Thematic reactive class",
        "base_health": 50,
        "base_mana": 30,
        "starting_skills": ["strength", "perception"],
    },
    "vanguard": {
        "description": "Melee bruiser or tank",
        "base_health": 60,
        "base_mana": 20,
        "starting_skills": ["strength", "willpower"],
    },
}

# Character origins
CHARACTER_ORIGINS = {
    "wasteland-born": {
        "description": "Born in the harsh wastelands, you've developed natural survival skills.",
        "passive": "Wasteland Resilience: +10% resistance to environmental effects",
    },
    "vault-bred": {
        "description": "Raised in the safety of a vault, you've received extensive education.",
        "passive": "Technical Expertise: +1 to knowledge checks",
    },
    "disgraced-noble": {
        "description": "Once part of the ruling class, now forced to survive on your own.",
        "passive": "Commanding Presence: +1 to social interactions with non-hostile NPCs",
    },
    "exiled-researcher": {
        "description": "A scientist who pushed boundaries too far and was cast out.",
        "passive": "Scientific Method: Can analyze unknown tech items without tools",
    },
    "forgotten-clone": {
        "description": "A clone created for unknown purposes, now seeking your own identity.",
        "passive": "Genetic Memory: Can attempt to recall information even without direct knowledge",
    },
    "sanctioned-hunter": {
        "description": "Trained to hunt down threats, you now work on your own terms.",
        "passive": "Tracker's Instinct: Can detect hidden enemies more easily",
    },
}

# Skills for skill checks
SKILLS = {
    "strength": "Physical power and might",
    "agility": "Dexterity, speed, and reflexes",
    "perception": "Awareness and observation",
    "willpower": "Mental fortitude and determination",
    "knowledge": "Education and information recall",
}

# Difficulty levels for skill checks
DIFFICULTY_LEVELS = {
    "trivial": 3,
    "easy": 4,
    "moderate": 5,
    "challenging": 6,
    "difficult": 7,
    "extreme": 8,
    "legendary": 9,
}

# Starting locations
STARTING_LOCATIONS = [
    "frozen_cathedral_entrance",
]

# Initial game areas
GAME_AREAS = {
    "frozen_cathedral": {
        "name": "The Frozen Cathedral",
        "description": "An ancient structure of ice and stone, humming with mysterious energy.",
        "locations": [
            "frozen_cathedral_entrance",
            "frozen_cathedral_main_hall",
            "frozen_cathedral_altar",
            "frozen_cathedral_eastern_corridor",
            "frozen_cathedral_western_passage",
            "frozen_cathedral_hidden_chamber",
        ]
    }
}

# Status effects
STATUS_EFFECTS = {
    "burning": {
        "description": "Taking fire damage over time",
        "effect_type": "damage_over_time",
        "value": 3,
        "max_duration": 3,
    },
    "frostbite": {
        "description": "Movement slowed by extreme cold",
        "effect_type": "movement_penalty",
        "value": -1,
        "max_duration": 4,
    },
    "focused": {
        "description": "Increased damage with abilities",
        "effect_type": "damage_bonus",
        "value": 0.1,  # 10% bonus
        "max_duration": 3,
    },
    "protected": {
        "description": "Damage reduction shield",
        "effect_type": "damage_reduction",
        "value": 0.2,  # 20% reduction
        "max_duration": 2,
    },
}

# Enemy types
ENEMY_TYPES = {
    "frost_guardian": {
        "name": "Frost Guardian",
        "description": "A massive construct of animated ice and stone", 
        "health": 60,
        "damage": 8,
        "abilities": ["ice_strike", "frost_armor"],
    },
    "ice_imp": {
        "name": "Ice Imp",
        "description": "A small, mischievous creature formed of crystalline ice",
        "health": 30,
        "damage": 5,
        "abilities": ["frost_shard", "blink"],
    },
}