# app/services/llm/factory.py
from typing import Optional
from .base import LLMAdapter
from .anthropic_adapter import AnthropicAdapter
from .mock_adapter import MockAdapter


class LLMAdapterFactory:
    """Factory class for creating LLM adapters."""

    @staticmethod
    def create_adapter(provider: str, config: Optional[dict] = None) -> LLMAdapter:
        """
        Create and return the appropriate LLM adapter.

        Args:
            provider: The LLM provider ("anthropic", "mock")
            config: Configuration options for the adapter

        Returns:
            An instance of the requested LLM adapter
        """
        config = config or {}

        if provider.lower() == "anthropic":
            api_key = config.get("api_key")
            if not api_key:
                raise ValueError("API key is required for Anthropic adapter")

            model = config.get("model", "claude-3-opus-20240229")
            timeout = config.get("timeout", 60)

            return AnthropicAdapter(api_key=api_key, model=model, timeout=timeout)

        elif provider.lower() == "mock":
            response_templates = config.get("response_templates")
            delay = config.get("delay", 0.5)

            return MockAdapter(response_templates=response_templates, delay=delay)

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
