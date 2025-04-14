# app/services/llm/mock_adapter.py
import json
import random
from typing import Dict, Any, Optional, List
import time
from .base import LLMAdapter


class MockAdapter(LLMAdapter):
    """Mock LLM adapter for testing and development."""

    def __init__(
        self, response_templates: Optional[Dict[str, Any]] = None, delay: float = 0.5
    ):
        """
        Initialize the mock adapter.

        Args:
            response_templates: Dictionary of predefined response templates
            delay: Simulated processing delay in seconds
        """
        self.delay = delay
        self.default_templates = {
            "exploration": {
                "action": "changeScene",
                "data": {
                    "locationId": "sample_location",
                    "description": "You find yourself in a dimly lit chamber. Ancient symbols adorn the walls, glowing faintly with an otherworldly light.",
                    "image": "ancient_chamber",
                    "suggestedActions": [
                        "Examine Symbols",
                        "Touch Glowing Wall",
                        "Continue Forward",
                        "Return",
                    ],
                },
            },
            "combat": {
                "action": "initiateCombat",
                "data": {
                    "enemies": [{"id": "shadow_guardian", "count": 1, "modifiers": []}],
                    "environment": "ancient_chamber",
                    "ambushState": "player_aware",
                    "introText": "As you step further into the chamber, the shadows coalesce, forming a guardian that blocks your path!",
                },
            },
            "dialogue": {
                "action": "npcInteraction",
                "data": {
                    "npcId": "ancient_keeper",
                    "dialogue": "Few venture this deep into the forgotten places. What do you seek here, traveler?",
                    "mood": "mysterious",
                    "options": [
                        {
                            "text": "I seek knowledge of the ancients.",
                            "intent": "knowledge_seeking",
                        },
                        {"text": "I'm just exploring.", "intent": "casual_exploration"},
                        {"text": "Who are you?", "intent": "identity_question"},
                    ],
                },
            },
            "error": {
                "success": False,
                "error": "Could not process the request",
                "details": "The mock LLM encountered a simulated error",
            },
        }

        # Merge provided templates with defaults
        self.response_templates = {**self.default_templates}
        if response_templates:
            self.response_templates.update(response_templates)

    async def generate_response(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate a mock response based on the prompt."""

        # Simulate processing time
        await self._simulate_delay()

        # Determine response type based on keywords in the prompt
        response_type = self._determine_response_type(prompt)

        # Randomly decide if we should simulate an error (5% chance)
        if random.random() < 0.05:
            return {
                "success": False,
                "error": "Simulated random error",
                "details": "This is a randomly generated error for testing error handling",
            }

        # Get the template for the determined response type
        template = self.response_templates.get(
            response_type, self.response_templates["exploration"]
        )

        # Add some randomness to make the responses feel different
        if response_type == "exploration":
            adjectives = [
                "mysterious",
                "ancient",
                "glowing",
                "dark",
                "strange",
                "ethereal",
                "pulsating",
            ]
            objects = [
                "symbols",
                "statues",
                "mechanisms",
                "crystals",
                "runes",
                "artifacts",
                "doorways",
            ]

            template["data"][
                "description"
            ] = f"You find yourself in a {random.choice(adjectives)} chamber. {random.choice(adjectives).capitalize()} {random.choice(objects)} can be seen around you, creating an atmosphere of wonder and caution."

        # Return success response with the template content
        return {
            "success": True,
            "content": json.dumps(template, indent=2),
            "raw_response": template,
        }

    async def parse_json_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the mock response (already in JSON format)."""
        if not response.get("success", False):
            return response

        # The content is already JSON in string format
        try:
            if isinstance(response.get("raw_response"), dict):
                # If we already have the raw_response as a dict, use that
                return {"success": True, "data": response["raw_response"]}
            else:
                # Otherwise, parse the content string
                parsed_data = json.loads(response["content"])
                return {"success": True, "data": parsed_data}
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Error parsing JSON response",
                "content": response.get("content", ""),
            }

    async def _simulate_delay(self):
        """Simulate processing delay."""
        # Use asyncio.sleep for async delay
        import asyncio

        await asyncio.sleep(self.delay * (0.5 + random.random()))

    def _determine_response_type(self, prompt: str) -> str:
        """Determine the appropriate response type based on the prompt content."""
        prompt_lower = prompt.lower()

        if any(
            word in prompt_lower
            for word in ["fight", "attack", "combat", "battle", "enemy"]
        ):
            return "combat"

        if any(
            word in prompt_lower
            for word in ["talk", "speak", "ask", "dialogue", "conversation"]
        ):
            return "dialogue"

        if random.random() < 0.1:  # 10% chance of error for testing
            return "error"

        # Default to exploration
        return "exploration"
