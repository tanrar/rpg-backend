# api/combat.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import random

from models.session import GameSession
from models.state import GameState
from services.session_service import SessionService
from services.llm_service import LLMService
from dependencies import get_session

router = APIRouter()
session_service = SessionService()
llm_service = LLMService()

class CombatActionRequest(BaseModel):
    """Request model for combat actions"""
    action_type: str  # attack, use_ability, use_item, defend, flee
    target_id: Optional[str] = None
    ability_id: Optional[str] = None
    item_id: Optional[str] = None

class CombatResponse(BaseModel):
    """Response model for combat endpoints"""
    description: str
    current_state: str
    combat_active: bool
    player_data: Dict[str, Any]
    enemies: List[Dict[str, Any]]
    initiative_order: List[str]
    current_turn: str
    round: int
    combat_log: List[str]
    available_actions: List[str]
    status_updates: Optional[Dict[str, Any]] = None
    narrative: Optional[str] = None

@router.post("/", response_model=CombatResponse)
async def perform_combat_action(
    action_request: CombatActionRequest,
    session: GameSession = Depends(get_session)
):
    """Process a combat action"""
    # Check if we're in the correct state
    if session.state != GameState.COMBAT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: Session is in {session.state} state, not COMBAT"
        )
    
    # Check if combat is active
    if not session.combat_state.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active combat"
        )
    
    # Check if it's the player's turn
    if session.combat_state.current_turn != "player":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="It's not the player's turn"
        )
    
    # Process the action
    action_type = action_request.action_type
    status_updates = {}
    narrative = ""
    
    if action_type == "attack":
        # Basic attack
        target_id = action_request.target_id
        
        # Validate target
        target_enemy = None
        for enemy in session.combat_state.enemies:
            if enemy["id"] == target_id:
                target_enemy = enemy
                break
        
        if not target_enemy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target: {target_id}"
            )
        
        # Calculate damage - basic formula for now
        base_damage = 5  # Base damage
        
        # Apply modifiers from status effects
        damage_modifier = 1.0
        for effect in session.player.status_effects:
            if effect.effect_type == "damage_bonus":
                damage_modifier += effect.value
        
        # Apply random variation (±20%)
        variation = random.uniform(0.8, 1.2)
        
        # Calculate final damage
        damage = int(base_damage * damage_modifier * variation)
        
        # Apply damage to enemy
        target_enemy["health"] -= damage
        
        # Check if enemy is defeated
        if target_enemy["health"] <= 0:
            target_enemy["health"] = 0
            session.combat_state.add_to_log(f"{target_enemy['name']} was defeated!")
            session.llm_context.add_key_event(f"Defeated {target_enemy['name']}")
            
            # Remove defeated enemy from initiative
            if target_enemy["id"] in session.combat_state.initiative_order:
                session.combat_state.initiative_order.remove(target_enemy["id"])
        
        # Add to combat log
        session.combat_state.add_to_log(f"Player attacks {target_enemy['name']} for {damage} damage.")
        
        # Update status
        status_updates = {
            "attack_result": {
                "target": target_enemy["name"],
                "damage": damage,
                "target_defeated": target_enemy["health"] <= 0
            }
        }
        
        # Generate narrative
        narrative = f"You strike at the {target_enemy['name']}, dealing {damage} damage."
        if target_enemy["health"] <= 0:
            narrative += f" The {target_enemy['name']} collapses before you."
    
    elif action_type == "use_ability":
        # Use a special ability
        ability_id = action_request.ability_id
        target_id = action_request.target_id
        
        # Find the ability
        ability = None
        for a in session.player.abilities:
            if a.id == ability_id:
                ability = a
                break
        
        if not ability:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ability not found: {ability_id}"
            )
        
        # Check if ability is on cooldown
        if ability.current_cooldown > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ability is on cooldown: {ability_id}"
            )
        
        # Check mana cost
        if session.player.mana < ability.mana_cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough mana for ability: {ability_id}"
            )
        
        # Find target if needed
        target_enemy = None
        if target_id:
            for enemy in session.combat_state.enemies:
                if enemy["id"] == target_id:
                    target_enemy = enemy
                    break
            
            if not target_enemy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid target: {target_id}"
                )
        
        # Apply ability effects - simplified for now
        # In a full implementation, abilities would have various effects
        
        # Example: damage ability
        damage = int(ability.effect.get("damage", 0))
        
        # Apply modifiers from status effects
        damage_modifier = 1.0
        for effect in session.player.status_effects:
            if effect.effect_type == "damage_bonus":
                damage_modifier += effect.value
        
        # Apply final damage
        damage = int(damage * damage_modifier)
        
        # Apply mana cost
        session.player.mana -= ability.mana_cost
        
        # Set cooldown
        ability.current_cooldown = ability.cooldown
        
        # Apply damage to target
        if target_enemy:
            target_enemy["health"] -= damage
            
            # Check if enemy is defeated
            if target_enemy["health"] <= 0:
                target_enemy["health"] = 0
                session.combat_state.add_to_log(f"{target_enemy['name']} was defeated!")
                session.llm_context.add_key_event(f"Defeated {target_enemy['name']} with {ability.name}")
                
                # Remove defeated enemy from initiative
                if target_enemy["id"] in session.combat_state.initiative_order:
                    session.combat_state.initiative_order.remove(target_enemy["id"])
            
            # Add to combat log
            session.combat_state.add_to_log(
                f"Player uses {ability.name} on {target_enemy['name']} for {damage} damage."
            )
            
            # Update status
            status_updates = {
                "ability_result": {
                    "ability": ability.name,
                    "target": target_enemy["name"],
                    "damage": damage,
                    "mana_cost": ability.mana_cost,
                    "target_defeated": target_enemy["health"] <= 0
                }
            }
            
            # Generate narrative
            narrative = f"You focus your energy and unleash {ability.name}, striking {target_enemy['name']} for {damage} damage."
            if target_enemy["health"] <= 0:
                narrative += f" The {target_enemy['name']} is destroyed by your power."
        
        # Example: healing ability
        healing = int(ability.effect.get("healing", 0))
        if healing > 0:
            old_health = session.player.health
            session.player.health = min(session.player.health + healing, session.player.max_health)
            actual_healing = session.player.health - old_health
            
            # Add to combat log
            session.combat_state.add_to_log(f"Player uses {ability.name} and heals for {actual_healing} health.")
            
            # Update status
            status_updates = {
                "ability_result": {
                    "ability": ability.name,
                    "healing": actual_healing,
                    "mana_cost": ability.mana_cost,
                }
            }
            
            # Generate narrative
            narrative = f"You focus your energy and use {ability.name}, restoring {actual_healing} health."
    
    elif action_type == "use_item":
        # Use an item
        item_id = action_request.item_id
        
        # Find the item
        item = None
        for i in session.player.inventory:
            if i.id == item_id:
                item = i
                break
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item not found: {item_id}"
            )
        
        # Apply item effects - simplified for now
        # In a full implementation, items would have various effects
        
        # Example: healing item
        if item.item_type == "healing":
            healing = int(item.properties.get("healing_amount", 10))
            old_health = session.player.health
            session.player.health = min(session.player.health + healing, session.player.max_health)
            actual_healing = session.player.health - old_health
            
            # Consume the item
            session.player.remove_item(item_id)
            
            # Add to combat log
            session.combat_state.add_to_log(f"Player uses {item.name} and heals for {actual_healing} health.")
            
            # Update status
            status_updates = {
                "item_result": {
                    "item": item.name,
                    "healing": actual_healing,
                    "item_consumed": True
                }
            }
            
            # Generate narrative
            narrative = f"You quickly use {item.name}, restoring {actual_healing} health."
        
        # Example: damage item
        elif item.item_type == "damage" and action_request.target_id:
            target_id = action_request.target_id
            
            # Find target
            target_enemy = None
            for enemy in session.combat_state.enemies:
                if enemy["id"] == target_id:
                    target_enemy = enemy
                    break
            
            if not target_enemy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid target: {target_id}"
                )
            
            # Apply damage
            damage = int(item.properties.get("damage_amount", 15))
            target_enemy["health"] -= damage
            
            # Consume the item
            session.player.remove_item(item_id)
            
            # Check if enemy is defeated
            if target_enemy["health"] <= 0:
                target_enemy["health"] = 0
                session.combat_state.add_to_log(f"{target_enemy['name']} was defeated!")
                session.llm_context.add_key_event(f"Defeated {target_enemy['name']} with {item.name}")
                
                # Remove defeated enemy from initiative
                if target_enemy["id"] in session.combat_state.initiative_order:
                    session.combat_state.initiative_order.remove(target_enemy["id"])
            
            # Add to combat log
            session.combat_state.add_to_log(
                f"Player uses {item.name} on {target_enemy['name']} for {damage} damage."
            )
            
            # Update status
            status_updates = {
                "item_result": {
                    "item": item.name,
                    "target": target_enemy["name"],
                    "damage": damage,
                    "item_consumed": True,
                    "target_defeated": target_enemy["health"] <= 0
                }
            }
            
            # Generate narrative
            narrative = f"You quickly use {item.name} against the {target_enemy['name']}, dealing {damage} damage."
            if target_enemy["health"] <= 0:
                narrative += f" The {target_enemy['name']} is destroyed."
    
    elif action_type == "defend":
        # Defensive stance - gain damage reduction for next round
        from models.player import StatusEffect
        
        # Create a defensive status effect
        defense_effect = StatusEffect(
            id="defended",
            name="Defensive Stance",
            description="Taking a defensive stance, reducing incoming damage",
            duration=1,  # Lasts until next turn
            effect_type="damage_reduction",
            value=0.5  # 50% damage reduction
        )
        
        # Apply to player
        session.player.add_status_effect(defense_effect)
        
        # Add to combat log
        session.combat_state.add_to_log("Player takes a defensive stance.")
        
        # Update status
        status_updates = {
            "defend_result": {
                "effect_applied": "Defensive Stance",
                "duration": 1,
                "damage_reduction": "50%"
            }
        }
        
        # Generate narrative
        narrative = "You brace yourself, taking a defensive stance against the incoming attacks."
    
    elif action_type == "flee":
        # Attempt to flee combat
        # Simple 50% chance of success for now
        success = random.random() < 0.5
        
        if success:
            # End combat
            session.combat_state.active = False
            
            # Transition back to exploration
            session.transition_to(GameState.EXPLORATION)
            
            # Add to combat log and LLM context
            session.combat_state.add_to_log("Player successfully flees from combat.")
            session.llm_context.add_key_event("Fled from combat")
            
            # Update status
            status_updates = {
                "flee_result": {
                    "success": True
                }
            }
            
            # Generate narrative
            narrative = "You find an opening and successfully escape from the battle."
        else:
            # Failed to flee
            # Add to combat log
            session.combat_state.add_to_log("Player fails to flee from combat.")
            
            # Update status
            status_updates = {
                "flee_result": {
                    "success": False
                }
            }
            
            # Generate narrative
            narrative = "You try to escape, but the enemies cut off your retreat!"
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type: {action_type}"
        )
    
    # End player's turn
    next_turn = session.combat_state.next_turn()
    
    # Add narrative to LLM context
    session.llm_context.add_narrative(narrative)
    
    # Check if combat has ended (all enemies defeated)
    remaining_enemies = [e for e in session.combat_state.enemies if e["health"] > 0]
    
    if not remaining_enemies:
        # End combat
        session.combat_state.active = False
        
        # Transition back to exploration
        session.transition_to(GameState.EXPLORATION)
        
        # Add to LLM context
        session.llm_context.add_key_event("Combat ended - all enemies defeated")
        
        # Add end of combat narrative
        narrative += " The battle is over, and you stand victorious."
    
    # If it's now an AI turn and combat is still active, process it
    if session.combat_state.active and next_turn != "player":
        # This would call an AI processing function
        # For now, we'll just do a simple implementation
        await _process_enemy_turn(session)
    
    # Save session
    session_service.update_session(session)
    
    # Filter out defeated enemies for the response
    active_enemies = [e for e in session.combat_state.enemies if e["health"] > 0]
    
    # Return response
    return {
        "description": narrative,
        "current_state": session.state,
        "combat_active": session.combat_state.active,
        "player_data": {
            "health": session.player.health,
            "max_health": session.player.max_health,
            "mana": session.player.mana,
            "max_mana": session.player.max_mana,
            "status_effects": [
                {
                    "id": effect.id,
                    "name": effect.name,
                    "description": effect.description,
                    "duration": effect.duration
                }
                for effect in session.player.status_effects
            ]
        },
        "enemies": active_enemies,
        "initiative_order": session.combat_state.initiative_order,
        "current_turn": session.combat_state.current_turn,
        "round": session.combat_state.round,
        "combat_log": session.combat_state.combat_log,
        "available_actions": session.get_allowed_actions() if session.state == GameState.COMBAT else [],
        "status_updates": status_updates,
        "narrative": narrative
    }

@router.get("/", response_model=CombatResponse)
async def get_combat_state(
    session: GameSession = Depends(get_session)
):
    """Get the current combat state"""
    # Check if we're in the correct state
    if session.state != GameState.COMBAT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: Session is in {session.state} state, not COMBAT"
        )
    
    # Check if combat is active
    if not session.combat_state.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active combat"
        )
    
    # Filter out defeated enemies for the response
    active_enemies = [e for e in session.combat_state.enemies if e["health"] > 0]
    
    # Determine available actions
    available_actions = session.get_allowed_actions()
    
    # If it's not the player's turn, they can't take actions
    if session.combat_state.current_turn != "player":
        available_actions = []
    
    # Return current state
    return {
        "description": "You are in combat.",
        "current_state": session.state,
        "combat_active": session.combat_state.active,
        "player_data": {
            "health": session.player.health,
            "max_health": session.player.max_health,
            "mana": session.player.mana,
            "max_mana": session.player.max_mana,
            "status_effects": [
                {
                    "id": effect.id,
                    "name": effect.name,
                    "description": effect.description,
                    "duration": effect.duration
                }
                for effect in session.player.status_effects
            ]
        },
        "enemies": active_enemies,
        "initiative_order": session.combat_state.initiative_order,
        "current_turn": session.combat_state.current_turn,
        "round": session.combat_state.round,
        "combat_log": session.combat_state.combat_log,
        "available_actions": available_actions,
        "narrative": None
    }

async def _process_enemy_turn(session: GameSession) -> None:
    """Process an enemy's turn in combat"""
    # Get the current enemy
    current_turn = session.combat_state.current_turn
    
    # Find the enemy
    current_enemy = None
    for enemy in session.combat_state.enemies:
        if enemy["id"] == current_turn:
            current_enemy = enemy
            break
    
    if not current_enemy:
        # Skip turn if enemy not found (shouldn't happen)
        session.combat_state.next_turn()
        return
    
    # Simple AI: just attack the player
    damage = current_enemy["damage"]
    
    # Apply random variation (±20%)
    variation = random.uniform(0.8, 1.2)
    damage = int(damage * variation)
    
    # Check if player has damage reduction
    damage_reduction = 0
    for effect in session.player.status_effects:
        if effect.effect_type == "damage_reduction":
            damage_reduction = max(damage_reduction, effect.value)
    
    # Apply damage reduction
    if damage_reduction > 0:
        damage = int(damage * (1 - damage_reduction))
        session.combat_state.add_to_log(
            f"Player's defensive stance reduces damage by {int(damage_reduction * 100)}%."
        )
    
    # Apply damage to player
    session.player.health -= damage
    
    # Ensure health doesn't go below 0
    session.player.health = max(0, session.player.health)
    
    # Add to combat log
    session.combat_state.add_to_log(
        f"{current_enemy['name']} attacks player for {damage} damage."
    )
    
    # Add narrative to LLM context
    narrative = f"The {current_enemy['name']} attacks you, dealing {damage} damage."
    session.llm_context.add_narrative(narrative)
    
    # Check if player is defeated
    if session.player.health <= 0:
        # Player is defeated - for now, we'll just end combat
        # In a more advanced game, this might trigger a game over or respawn
        session.combat_state.active = False
        
        # Transition back to exploration
        session.transition_to(GameState.EXPLORATION)
        
        # Add to LLM context
        session.llm_context.add_key_event("Player was defeated in combat")
        
        # Restore some health to allow continued play
        session.player.health = max(1, int(session.player.max_health * 0.2))
        
        # Add to combat log
        session.combat_state.add_to_log("Player was defeated but manages to escape.")
        
        return
    
    # Move to next turn
    session.combat_state.next_turn()
    
    # If it's still an enemy turn, process it recursively
    if session.combat_state.active and session.combat_state.current_turn != "player":
        await _process_enemy_turn(session)