"""
Model capabilities registry for PageIndex (TARGET 1.4).
Defines capabilities and constraints for OpenAI and Ollama models.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Constants
DEFAULT_3B_MODEL = "mistral24b-16k"


@dataclass
class ModelCapabilities:
    """Define capabilities and constraints for each model"""
    
    name: str
    provider: str
    context_window: int
    supports_json_mode: bool
    supports_streaming: bool
    temperature_range: tuple = (0.0, 2.0)
    max_output_tokens: Optional[int] = None
    estimated_tokens_per_second: float = 10.0  # Average throughput
    parameter_count: str = "unknown"  # e.g., "3.8B", "7B"
    
    def validate_prompt_tokens(self, token_count: int) -> bool:
        """Check if prompt fits in context window"""
        # Reserve 20% for output
        max_input = int(self.context_window * 0.8)
        return token_count <= max_input
    
    def get_safe_chunk_size(self) -> int:
        """Get safe text chunk size for this model"""
        # Assume ~4 characters per token (English text average)
        chars_per_token = 4
        # Use 70% of context window for safety
        safe_tokens = int(self.context_window * 0.7)
        return safe_tokens * chars_per_token
    
    def estimate_processing_time(self, token_count: int) -> float:
        """Estimate processing time in seconds"""
        if self.estimated_tokens_per_second <= 0:
            return 0.0
        return token_count / self.estimated_tokens_per_second
    
    def __str__(self) -> str:
        return f"{self.name} ({self.parameter_count}, {self.provider})"


# Model registry - comprehensive list of supported models
MODEL_REGISTRY: Dict[str, ModelCapabilities] = {
    # OpenAI Models
    "gpt-4o-2024-11-20": ModelCapabilities(
        name="gpt-4o-2024-11-20",
        provider="openai",
        context_window=128000,
        supports_json_mode=True,
        supports_streaming=True,
        estimated_tokens_per_second=100.0,
        parameter_count="unknown"
    ),
    "gpt-4o": ModelCapabilities(
        name="gpt-4o",
        provider="openai",
        context_window=128000,
        supports_json_mode=True,
        supports_streaming=True,
        estimated_tokens_per_second=100.0,
        parameter_count="unknown"
    ),
    "gpt-3.5-turbo": ModelCapabilities(
        name="gpt-3.5-turbo",
        provider="openai",
        context_window=16384,
        supports_json_mode=True,
        supports_streaming=True,
        estimated_tokens_per_second=150.0,
        parameter_count="unknown"
    ),
    
    # Ollama Models - Small (< 4B parameters)
    "phi3:3.8b": ModelCapabilities(
        name="phi3:3.8b",
        provider="ollama",
        context_window=4096,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=50.0,
        parameter_count="3.8B",
        max_output_tokens=2048
    ),
    "phi3": ModelCapabilities(  # Alias for phi3:3.8b
        name="phi3",
        provider="ollama",
        context_window=4096,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=50.0,
        parameter_count="3.8B",
        max_output_tokens=2048
    ),
    "gemma:2b": ModelCapabilities(
        name="gemma:2b",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=75.0,
        parameter_count="2B",
        max_output_tokens=4096
    ),
    "gemma:3b": ModelCapabilities(
        name="gemma:3b",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=60.0,
        parameter_count="3B",
        max_output_tokens=4096
    ),
    "stablelm2:1.6b": ModelCapabilities(
        name="stablelm2:1.6b",
        provider="ollama",
        context_window=4096,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=85.0,
        parameter_count="1.6B",
        max_output_tokens=2048
    ),
    
    # Ollama Models - Medium (4B-10B parameters)
    "mistral:7b": ModelCapabilities(
        name="mistral:7b",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=40.0,
        parameter_count="7B",
        max_output_tokens=4096
    ),
    "mistral": ModelCapabilities(  # Alias for mistral:7b
        name="mistral",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=40.0,
        parameter_count="7B",
        max_output_tokens=4096
    ),
    "llama3:8b": ModelCapabilities(
        name="llama3:8b",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=35.0,
        parameter_count="8B",
        max_output_tokens=4096
    ),
    "llama3": ModelCapabilities(  # Alias for llama3:8b
        name="llama3",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=35.0,
        parameter_count="8B",
        max_output_tokens=4096
    ),
    
    # Ollama Models - Large (> 10B parameters)
    "mistral24b-16k": ModelCapabilities(
        name="mistral24b-16k",
        provider="ollama",
        context_window=16384,  # 16k context window
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=25.0,
        parameter_count="24B",
        max_output_tokens=16384
    ),
    "mistral24b-prod": ModelCapabilities(
        name="mistral24b-prod",
        provider="ollama",
        context_window=16384,  # 16k context window (production-constrained)
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=25.0,  # Slightly slower than 14B
        parameter_count="24B",
        max_output_tokens=512  # Constrained for production
    ),
    "mistral-small:24b": ModelCapabilities(
        name="mistral-small:24b",
        provider="ollama",
        context_window=32768,  # 32k context window (base model)
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=25.0,
        parameter_count="24B",
        max_output_tokens=4096
    ),
    "mistral-small": ModelCapabilities(  # Alias for mistral-small:24b
        name="mistral-small",
        provider="ollama",
        context_window=32768,  # 32k context window
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=25.0,
        parameter_count="24B",
        max_output_tokens=4096
    ),
    "qwen2.5:14b": ModelCapabilities(
        name="qwen2.5:14b",
        provider="ollama",
        context_window=131072,  # 128k context window
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=30.0,
        parameter_count="14B",
        max_output_tokens=32768
    ),
    "qwen2.5": ModelCapabilities(  # Alias for qwen2.5:14b
        name="qwen2.5",
        provider="ollama",
        context_window=131072,  # 128k context window
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=30.0,
        parameter_count="14B",
        max_output_tokens=32768
    ),
    "mixtral:8x7b": ModelCapabilities(
        name="mixtral:8x7b",
        provider="ollama",
        context_window=32768,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=25.0,
        parameter_count="46.7B",
        max_output_tokens=16384
    ),
    "llama3:70b": ModelCapabilities(
        name="llama3:70b",
        provider="ollama",
        context_window=8192,
        supports_json_mode=False,
        supports_streaming=True,
        estimated_tokens_per_second=5.0,
        parameter_count="70B",
        max_output_tokens=4096
    ),
}


def get_model_capabilities(model_name: str) -> ModelCapabilities:
    """
    Get capabilities for a specific model.
    
    Args:
        model_name: Model identifier (e.g., "phi3:3.8b", "gpt-4o")
    
    Returns:
        ModelCapabilities object
    
    Raises:
        ValueError: If model is not in registry
    """
    if model_name not in MODEL_REGISTRY:
        logger.warning(f"Unknown model: {model_name}, using default capabilities")
        # Return default fallback capabilities
        return ModelCapabilities(
            name=model_name,
            provider="unknown",
            context_window=4096,
            supports_json_mode=False,
            supports_streaming=True,
            estimated_tokens_per_second=20.0,
            parameter_count="unknown"
        )
    return MODEL_REGISTRY[model_name]


def list_models_by_provider(provider: str) -> list:
    """
    List all models for a specific provider.
    
    Args:
        provider: Provider name ("openai" or "ollama")
    
    Returns:
        List of model names
    """
    return [
        name for name, caps in MODEL_REGISTRY.items()
        if caps.provider == provider
    ]


def get_recommended_model(provider: str, parameter_limit: Optional[int] = None) -> str:
    """
    Get recommended model for provider with optional parameter limit.
    
    Args:
        provider: Provider name ("openai" or "ollama")
        parameter_limit: Max parameter count in billions (e.g., 4 for 4B)
    
    Returns:
        Recommended model name
    """
    if provider == "openai":
        return "gpt-4o-mini"  # OpenAI lightweight model
    
    elif provider == "ollama":
        if parameter_limit is None:
            return DEFAULT_3B_MODEL  # Default 3B model
        
        # Filter by parameter limit
        suitable_models = []
        for name, caps in MODEL_REGISTRY.items():
            if caps.provider != "ollama":
                continue
            
            # Parse parameter count (e.g., "3.8B" -> 3.8)
            param_str = caps.parameter_count
            if param_str == "unknown":
                continue
            
            try:
                param_count = float(param_str.rstrip("B"))
                if param_count <= parameter_limit:
                    suitable_models.append((name, param_count, caps.context_window))
            except ValueError:
                continue
        
        if not suitable_models:
            return DEFAULT_3B_MODEL  # Fallback
        
        # Sort by parameter count (descending) then context window
        suitable_models.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return suitable_models[0][0]
    
    else:
        raise ValueError(f"Unknown provider: {provider}")


def validate_model_for_task(model_name: str, required_context: int) -> bool:
    """
    Validate if a model is suitable for a task with given context requirements.
    
    Args:
        model_name: Model identifier
        required_context: Required context window in tokens
    
    Returns:
        True if model is suitable, False otherwise
    """
    try:
        caps = get_model_capabilities(model_name)
        return caps.validate_prompt_tokens(required_context)
    except ValueError:
        return False
