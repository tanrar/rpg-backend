# app/services/llm/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class LLMAdapter(ABC):
    """Base abstract class for LLM service adapters."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM based on the prompt and context.

        Args:
            prompt: The main prompt to send to the LLM
            context: Optional list of previous messages for context
            max_tokens: Maximum number of tokens in the response
            temperature: Controls randomness (0 = deterministic, 1 = creative)

        Returns:
            Dict containing the LLM response and metadata
        """
        pass

    @abstractmethod
    async def parse_json_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the LLM response to extract structured JSON data.

        Args:
            response: The raw response from the LLM

        Returns:
            Parsed JSON data from the response
        """
        pass
