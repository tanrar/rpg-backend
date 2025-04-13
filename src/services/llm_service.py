# services/llm_service.py
import json
import os
from typing import Dict, List, Any, Optional
import asyncio

from config.settings import Settings
from models.session import GameSession, LLMContext

class LLMService:
    """Service for interacting with the LLM for game narrative"""
    
    def __init__(self):
        """Initialize the LLM service"""
        self.settings = Settings()
        self.client = self._initialize_client()
    
    def _initialize_client(self) -> Any:
        """Initialize the appropriate LLM client based on settings"""
        # This is a placeholder - you'll need to replace with actual client initialization
        # based on your chosen LLM provider
        
        if self.settings.llm_provider == "openai":
            try:
                import openai
                openai.api_key = self.settings.llm_api_key
                return openai
            except ImportError:
                print("OpenAI package not installed. Install with: pip install openai")
                return None
                
        elif self.settings.llm_provider == "anthropic":
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.settings.llm_api_key)
            except ImportError:
                print("Anthropic package not installed. Install with: pip install anthropic")
                return None
                
        else:
            print(f"Unsupported LLM provider: {self.settings.llm_provider}")
            return None
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM"""
        return """
        You are the narrative engine for an RPG game set in a post-apocalyptic world with 
        elements of science fiction and mysticism. You should interpret player actions, 
        generate vivid scene descriptions, and determine appropriate outcomes based on 
        the game's context and rules.
        
        You will receive information about the player's character, current location, and action.
        You should respond with JSON that includes a narrative description and game commands.
        
        Your responses should be evocative and atmospheric, but also concise and focused on 
        advancing the narrative based on player actions.
        
        You never break character or acknowledge that you're an AI. You are the storyteller
        and dungeon master, guiding the player through this world.
        """
    
    def _build_prompt(self, session: GameSession, player_action: str) -> str:
        """Build the prompt for the LLM based on the current game state"""
        # Build context from world state and player info
        context = self._build_context(session)
        
        # Add the player action
        prompt = f"""
        {context}
        
        Player action: {player_action}
        
        Respond with a JSON object that contains:
        1. A "description" field with your narrative response
        2. An "action" field with a game engine command (changeScene, skillCheck, etc.)
        3. A "data" field with parameters for the action
        
        For example:
        ```json
        {{
          "description": "The beacon pulses with energy as you approach...",
          "action": "environmentInteraction",
          "data": {{
            "interactionType": "examine",
            "targetId": "frozen_beacon",
            "description": "The beacon's surface is cold to the touch...",
            "suggestedActions": ["Touch Crystal", "Step Back", "Use Echo Key"]
          }}
        }}
        ```
        """
        
        return prompt
    
    def _build_context(self, session: GameSession) -> str:
        """Build context information for the LLM"""
        # Get current location
        current_location = session.world_state.locations.get(session.current_location)
        if not current_location:
            return "Error: Current location not found"
            
        # Get NPCs in the current location
        npcs_in_location = [
            session.world_state.npcs[npc_id] 
            for npc_id in current_location.npcs 
            if npc_id in session.world_state.npcs
        ]
        
        # Build context
        context = f"""
        ## Player Information
        Name: {session.player.name}
        Class: {session.player.character_class}
        Origin: {session.player.origin}
        Level: {session.player.level}
        Health: {session.player.health}/{session.player.max_health}
        Mana: {session.player.mana}/{session.player.max_mana}
        
        ## Current Location
        Name: {current_location.name}
        Description: {current_location.description}
        
        ## NPCs Present
        {', '.join([npc.name for npc in npcs_in_location]) if npcs_in_location else 'None'}
        
        ## Objects in Area
        {', '.join([obj['name'] for obj in current_location.interactive_objects]) if current_location.interactive_objects else 'None'}
        
        ## Items in Area
        {', '.join([item['name'] for item in current_location.items]) if current_location.items else 'None'}
        
        ## Connected Locations
        {', '.join([session.world_state.locations[loc].name for loc in current_location.connections if loc in session.world_state.locations])}
        
        ## Recent History
        {self._format_history(session.llm_context)}
        
        ## Game State
        Current State: {session.state.value}
        """
        
        # Add combat information if in combat
        if session.state.value == "combat" and session.combat_state.active:
            combat_context = f"""
            ## Combat Information
            Enemies: {', '.join([enemy['name'] for enemy in session.combat_state.enemies])}
            Current Turn: {session.combat_state.current_turn}
            Round: {session.combat_state.round}
            """
            context += combat_context
            
        # Add dialogue information if in dialogue
        if session.state.value == "dialogue" and session.dialogue_state.active:
            npc_id = session.dialogue_state.npc_id
            npc = session.world_state.npcs.get(npc_id) if npc_id else None
            
            if npc:
                dialogue_context = f"""
                ## Dialogue Information
                Speaking with: {npc.name}
                Description: {npc.description}
                """
                
                # Add recent conversation history
                if session.dialogue_state.conversation_history:
                    dialogue_context += "\n## Recent Conversation\n"
                    recent_exchanges = session.dialogue_state.conversation_history[-5:]  # Last 5 exchanges
                    for exchange in recent_exchanges:
                        dialogue_context += f"{exchange['speaker']}: {exchange['text']}\n"
                        
                context += dialogue_context
        
        return context
    
    def _format_history(self, llm_context: LLMContext) -> str:
        """Format the history from LLM context"""
        history = ""
        
        # Add narrative history (last 3 entries)
        if llm_context.narrative_history:
            history += "Recent narrative:\n"
            for entry in llm_context.narrative_history[-3:]:
                history += f"- {entry['text']}\n"
        
        # Add action history (last 3 entries)
        if llm_context.action_history:
            history += "\nRecent actions:\n"
            for entry in llm_context.action_history[-3:]:
                history += f"- {entry['action']} → {entry['result']}\n"
        
        # Add key events (last 5)
        if llm_context.key_events:
            history += "\nKey events:\n"
            for event in llm_context.key_events[-5:]:
                history += f"- {event}\n"
                
        return history
    
    async def process_action(self, session: GameSession, player_action: str) -> Dict[str, Any]:
        """Process a player action through the LLM and return a structured response"""
        # Build the prompt
        prompt = self._build_prompt(session, player_action)
        
        # If we have no client, return error response
        if not self.client:
            return {
                "description": "Error: LLM client not initialized. Check your configuration.",
                "action": "error",
                "data": {}
            }
        
        try:
            # Call the appropriate LLM based on provider
            if self.settings.llm_provider == "openai":
                response = await self._call_openai(prompt)
            elif self.settings.llm_provider == "anthropic":
                response = await self._call_anthropic(prompt)
            else:
                return {
                    "description": f"Error: Unsupported LLM provider: {self.settings.llm_provider}",
                    "action": "error",
                    "data": {}
                }
                
            # Parse the JSON response
            try:
                # Add parsed response to LLM context
                session.llm_context.add_narrative(response.get("description", ""))
                session.llm_context.add_action(player_action, response.get("description", ""))
                
                return response
            except json.JSONDecodeError:
                return {
                    "description": "Error: Could not parse LLM response as JSON.",
                    "action": "error",
                    "data": {}
                }
                
        except Exception as e:
            return {
                "description": f"Error communicating with LLM: {str(e)}",
                "action": "error",
                "data": {}
            }
    
    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Make an API call to OpenAI"""
        try:
            response = await asyncio.to_thread(
                self.client.ChatCompletion.create,
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.choices[0].message.content
            
            # Extract JSON from the response
            try:
                # Handle case where LLM wraps JSON in ```json blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                return json.loads(content)
            except json.JSONDecodeError:
                return {
                    "description": "Error: Could not parse LLM response as JSON.",
                    "action": "error",
                    "data": {}
                }
                
        except Exception as e:
            return {
                "description": f"Error calling OpenAI: {str(e)}",
                "action": "error",
                "data": {}
            }
    
    async def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        """Make an API call to Anthropic"""
        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.settings.llm_model,
                system=self._build_system_prompt(),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            
            # Extract JSON from the response
            try:
                # Handle case where LLM wraps JSON in ```json blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                return json.loads(content)
            except json.JSONDecodeError:
                return {
                    "description": "Error: Could not parse LLM response as JSON.",
                    "action": "error",
                    "data": {}
                }
                
        except Exception as e:
            return {
                "description": f"Error calling Anthropic: {str(e)}",
                "action": "error",
                "data": {}
            }