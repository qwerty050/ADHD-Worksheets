"""
Response handler and finish reason normalization for PageIndex (TARGET 1.5 support).
Provides provider-agnostic response handling and finish reason normalization.
"""

from enum import Enum
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FinishReason(Enum):
    """Normalized finish reason across all providers"""
    FINISHED = "finished"  # Natural completion
    MAX_OUTPUT = "max_output_reached"  # Truncated due to token limit
    ERROR = "error"  # Error occurred
    CONTENT_FILTER = "content_filter"  # Safety filter triggered
    UNKNOWN = "unknown"  # Unknown status


class ResponseHandler:
    """Handle responses from different providers"""
    
    @staticmethod
    def normalize_finish_reason(
        provider_name: str,
        raw_reason: Optional[str]
    ) -> FinishReason:
        """
        Convert provider-specific finish_reason to standard
        
        Args:
            provider_name: Name of the provider ("openai", "ollama", etc.)
            raw_reason: Raw finish reason from provider
        
        Returns:
            Normalized FinishReason enum value
        """
        
        if provider_name == "openai":
            if raw_reason == "stop":
                return FinishReason.FINISHED
            elif raw_reason == "length":
                return FinishReason.MAX_OUTPUT
            elif raw_reason == "content_filter":
                return FinishReason.CONTENT_FILTER
            else:
                return FinishReason.FINISHED
        
        elif provider_name == "ollama":
            # Ollama doesn't have native finish_reason
            # The inferred value comes from OllamaProvider._infer_finish_reason()
            if raw_reason == "max_output_reached":
                return FinishReason.MAX_OUTPUT
            elif raw_reason == "finished":
                return FinishReason.FINISHED
            else:
                return FinishReason.FINISHED
        
        else:
            return FinishReason.UNKNOWN
    
    @staticmethod
    def should_continue(finish_reason: FinishReason) -> bool:
        """
        Check if output should be continued (more tokens expected)
        
        Args:
            finish_reason: Normalized finish reason
        
        Returns:
            True if continuation should be attempted
        """
        return finish_reason == FinishReason.MAX_OUTPUT
    
    @staticmethod
    def should_continue_str(finish_reason_str: str) -> bool:
        """
        Check if output should be continued (string version)
        
        Args:
            finish_reason_str: Finish reason as string value
        
        Returns:
            True if continuation should be attempted
        """
        return finish_reason_str == "max_output_reached"
