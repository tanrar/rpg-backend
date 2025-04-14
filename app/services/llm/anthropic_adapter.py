# app/services/llm/anthropic_adapter.py
import json
from typing import Dict, Any, Optional, List
import httpx
import logging
from .base import LLMAdapter

logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic's Claude LLM API."""

    def __init__(
        self, api_key: str, model: str = "claude-3-opus-20240229", timeout: int = 60
    ):
        """
        Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def generate_response(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate a response from Claude based on the prompt and context."""

        # Format messages for Anthropic API
        messages = []

        # Add context messages if provided
        if context:
            for message in context:
                messages.append(message)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Prepare request data
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=data, headers=headers)

                if response.status_code != 200:
                    logger.error(
                        f"Anthropic API error: {response.status_code} - {response.text}"
                    )
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": response.text,
                    }

                response_data = response.json()
                return {
                    "success": True,
                    "content": response_data["content"][0]["text"],
                    "raw_response": response_data,
                }

        except Exception as e:
            logger.exception("Error calling Anthropic API")
            return {"success": False, "error": str(e), "details": str(e)}

    async def parse_json_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the Claude response to extract structured JSON data."""
        if not response.get("success", False):
            return {
                "success": False,
                "error": response.get("error", "Unknown error"),
                "details": response.get("details", "No details available"),
            }

        content = response.get("content", "")

        # Try to extract JSON from the response
        try:
            # Look for JSON content between triple backticks
            json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
            import re

            match = re.search(json_pattern, content)

            if match:
                json_str = match.group(1)
                parsed_data = json.loads(json_str)
                return {"success": True, "data": parsed_data}

            # If no JSON in code blocks, try to find JSON directly in the text
            # This is a fallback and may be less reliable
            try:
                # Find anything that looks like a JSON object
                json_pattern = r"\{[\s\S]*\}"
                match = re.search(json_pattern, content)
                if match:
                    json_str = match.group(0)
                    parsed_data = json.loads(json_str)
                    return {"success": True, "data": parsed_data}
            except:
                pass

            return {
                "success": False,
                "error": "No valid JSON found in response",
                "content": content,
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON decode error: {str(e)}",
                "content": content,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parsing response: {str(e)}",
                "content": content,
            }
