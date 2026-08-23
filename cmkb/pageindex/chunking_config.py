"""
Adaptive chunking configuration for large PDF processing.
Automatically adjusts thresholds based on model capabilities.
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ChunkingConfig:
    """
    Configuration for adaptive document chunking.
    Thresholds are dynamically calculated based on model's max output tokens.
    """
    
    def __init__(self, max_output_tokens: int = 4096):
        """
        Initialize chunking config.
        
        Args:
            max_output_tokens: Model's maximum output token limit
                             (e.g., 4096 for standard, 16384 for 16K model)
        """
        self.max_output_tokens = max_output_tokens
        self._init_thresholds()
    
    def _init_thresholds(self):
        """Calculate all thresholds based on max output tokens."""
        
        # TOC thresholds (in characters)
        # Rule: max input + output should stay within context
        # 16K context window = 16384 tokens
        # Reserve: inputs ~3-4K tokens, outputs vary
        # So for safety, cap at: (16384 - 4000) tokens input
        if self.max_output_tokens >= 16000:
            # 16K model: can handle much larger TOCs before chunking
            self.toc_single_pass_threshold = 35000  # ~8K tokens input, leaves 8K for output
            self.toc_chunk_size = 25000  # Fewer, larger chunks
        elif self.max_output_tokens >= 8000:
            # 8K model: moderate thresholds
            self.toc_single_pass_threshold = 20000
            self.toc_chunk_size = 12000
        else:
            # 4K model (default): conservative thresholds
            self.toc_single_pass_threshold = 12000
            self.toc_chunk_size = 8000
        
        # No-TOC document thresholds
        # These determine when to use hierarchical (chunked) processing
        if self.max_output_tokens >= 16000:
            # 16K: can handle much larger documents before needing chunks
            # TOC: comfortable single-pass with room for large JSON output (~4K tokens)
            # No-TOC: very large documents, hierarchical only when truly needed
            self.no_toc_page_threshold = 300  # Up from 120 pages (16K can inhale big documents)
            self.no_toc_token_threshold = 250000  # Up from 80K tokens (16K context is generous)
            self.no_toc_chunk_size = 120  # Larger chunks with minimal overlaps
            self.no_toc_overlap_pages = 2  # Slight overlap for seamless merging
        elif self.max_output_tokens >= 8000:
            # 8K model
            self.no_toc_page_threshold = 180
            self.no_toc_token_threshold = 120000
            self.no_toc_chunk_size = 60
            self.no_toc_overlap_pages = 1
        else:
            # 4K model (default)
            self.no_toc_page_threshold = 120
            self.no_toc_token_threshold = 80000
            self.no_toc_chunk_size = 40
            self.no_toc_overlap_pages = 1
    
    def __repr__(self) -> str:
        return (
            f"ChunkingConfig("
            f"max_output_tokens={self.max_output_tokens}, "
            f"toc_threshold={self.toc_single_pass_threshold}chars, "
            f"toc_chunk={self.toc_chunk_size}chars, "
            f"no_toc_threshold={self.no_toc_page_threshold}pages/{self.no_toc_token_threshold}tokens, "
            f"no_toc_chunk={self.no_toc_chunk_size}pages"
            f")"
        )
    
    def log_config(self, logger=None):
        """Log current configuration."""
        if logger is None:
            logger = logging.getLogger(__name__)
        
        logger.info(f"ChunkingConfig initialized: {self}")
        logger.info(f"  TOC: single-pass up to {self.toc_single_pass_threshold} chars, "
                   f"chunks of {self.toc_chunk_size} chars")
        logger.info(f"  No-TOC: triggers at {self.no_toc_page_threshold} pages or "
                   f"{self.no_toc_token_threshold} tokens, "
                   f"{self.no_toc_chunk_size}-page chunks")


def get_chunking_config_for_model(model_name: str) -> ChunkingConfig:
    """
    Get chunking configuration for a specific model.
    
    Args:
        model_name: Model identifier (e.g., 'mistral24b-prod', 'mistral24b-16k')
    
    Returns:
        ChunkingConfig with appropriate thresholds
    """
    model_name = model_name.lower() if model_name else ""
    
    # Map model names to output token limits
    if "32k" in model_name:
        max_tokens = 32768
    elif "16k" in model_name:
        max_tokens = 16384
    elif "8k" in model_name:
        max_tokens = 8192
    else:
        # Default to conservative 4K for unknown models
        max_tokens = 4096
    
    logger.info(f"Selected chunking config for model '{model_name}': "
               f"max_output_tokens={max_tokens}")
    
    return ChunkingConfig(max_output_tokens=max_tokens)


def get_chunking_config_from_capabilities(model_capabilities: dict) -> ChunkingConfig:
    """
    Get chunking configuration from model capabilities dict.
    
    Args:
        model_capabilities: Dict with 'max_output_tokens' key
    
    Returns:
        ChunkingConfig with appropriate thresholds
    """
    max_tokens = model_capabilities.get('max_output_tokens', 4096)
    return ChunkingConfig(max_output_tokens=max_tokens)


# Default configurations for common models
DEFAULT_CONFIGS = {
    'mistral24b-prod': ChunkingConfig(max_output_tokens=4096),
    'mistral24b-16k': ChunkingConfig(max_output_tokens=16384),
    'mistral-small': ChunkingConfig(max_output_tokens=4096),
    'gpt-4': ChunkingConfig(max_output_tokens=8192),
    'gpt-4-turbo': ChunkingConfig(max_output_tokens=4096),
}
