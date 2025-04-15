# app/services/llm/factory.py (update)
from typing import Optional
from .base import LLMAdapter
from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter
from .mock_adapter import MockAdapter
from app.config.settings import Settings

class LLMAdapterFactory:
    """Factory class for creating LLM adapters."""
    
    @staticmethod
    def create_adapter() -> LLMAdapter:
        """
        Create and return the appropriate LLM adapter.
        
        Args:
            provider: The LLM provider ("anthropic", "gemini", "mock")
            config: Configuration options for the adapter
            
        Returns:
            An instance of the requested LLM adapter
        """
        settings = Settings()
        provider = settings.llm_provider
        if provider.lower() == "anthropic":
            api_key = settings.anthropic_api_key
            if not api_key:
                raise ValueError("API key is required for Anthropic adapter")
                
            model = settings.anthropic_model
            if not model:
                raise ValueError("Model is required for Anthropic adapter")
            timeout = 60
            
            return AnthropicAdapter(api_key=api_key, model=model, timeout=timeout)
        
        elif provider.lower() == "gemini":
            api_key = settings.gemini_api_key
            if not api_key:
                raise ValueError("API key is required for Gemini adapter")
                
            model = settings.gemini_model
            if not model:
                raise ValueError("Model is required for Gemini adapter")
            timeout = 60
            
            return GeminiAdapter(api_key=api_key, model=model, timeout=timeout)
            
        elif provider.lower() == "mock":
            
            return MockAdapter(response_templates={}, delay=5)
            
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")