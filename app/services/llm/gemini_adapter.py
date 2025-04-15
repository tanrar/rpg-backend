# app/services/llm/gemini_adapter.py
import json
from typing import Dict, Any, Optional, List
import httpx
import logging
from .base import LLMAdapter

logger = logging.getLogger(__name__)

class GeminiAdapter(LLMAdapter):
    """Adapter for Google's Gemini LLM API."""
    
    def __init__(self, api_key: str, model: str = "gemini-pro", timeout: int = 60):
        """
        Initialize the Gemini adapter.
        
        Args:
            api_key: Google API key
            model: Gemini model to use (gemini-pro, gemini-ultra, etc.)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
        
    async def generate_response(self, 
                               prompt: str, 
                               context: Optional[List[Dict[str, str]]] = None, 
                               max_tokens: int = 1000,
                               temperature: float = 0.7) -> Dict[str, Any]:
        """Generate a response from Gemini based on the prompt and context."""
        
        # Format messages for Gemini API
        contents = []
        
        # Add context messages if provided
        if context:
            for message in context:
                role = "user" if message.get("role", "") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": message.get("content", "")}]
                })
        
        # Add current prompt
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Prepare request data
        data = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }
        
        # Build URL with API key
        url = f"{self.base_url}?key={self.api_key}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Sending request to Gemini API: {self.model}")
                
                response = await client.post(
                    url,
                    json=data,
                    headers={"Content-Type": "application/json"}
                )
                
                logger.info(f"Gemini API response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": response.text
                    }
                
                response_data = response.json()
                
                # Extract text from Gemini response
                text = ""
                if "candidates" in response_data and len(response_data["candidates"]) > 0:
                    candidate = response_data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        for part in parts:
                            if "text" in part:
                                text += part["text"]
                
                # Log response preview
                text_preview = text[:100] + "..." if len(text) > 100 else text
                logger.info(f"Gemini API response preview: {text_preview}")
                
                return {
                    "success": True,
                    "content": text,
                    "raw_response": response_data
                }
                
        except Exception as e:
            logger.exception(f"Error calling Gemini API: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "details": str(e)
            }
    
    async def parse_json_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the Gemini response to extract structured JSON data."""
        if not response.get("success", False):
            return {
                "success": False,
                "error": response.get("error", "Unknown error"),
                "details": response.get("details", "No details available")
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
                return {
                    "success": True,
                    "data": parsed_data
                }
            
            # If no JSON in code blocks, try to find JSON directly in the text
            try:
                # Find anything that looks like a JSON object
                json_pattern = r"\{[\s\S]*\}"
                match = re.search(json_pattern, content)
                if match:
                    json_str = match.group(0)
                    parsed_data = json.loads(json_str)
                    return {
                        "success": True,
                        "data": parsed_data
                    }
            except:
                pass
                
            return {
                "success": False,
                "error": "No valid JSON found in response",
                "content": content
            }
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON decode error: {str(e)}",
                "content": content
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parsing response: {str(e)}",
                "content": content
            }