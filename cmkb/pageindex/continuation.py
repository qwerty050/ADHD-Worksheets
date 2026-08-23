"""
Continuation handler for managing multi-turn conversations with truncation detection.
Handles output continuation when responses are truncated due to token limits (TARGET 1.5).
"""

import logging
from typing import Callable, Tuple, Optional

logger = logging.getLogger(__name__)


class ContinuationHandler:
    """Handle multi-turn conversations with truncation detection"""
    
    def __init__(self, max_iterations: int = 10):
        """
        Initialize continuation handler
        
        Args:
            max_iterations: Maximum number of continuation attempts
        """
        self.max_iterations = max_iterations
        self.iteration_count = 0
        self.accumulated_content = ""
    
    def should_continue(self, finish_reason: str) -> bool:
        """
        Check if we should request more output
        
        Args:
            finish_reason: Finish reason string ("finished", "max_output_reached", "error")
        
        Returns:
            True if continuation should be attempted
        """
        
        if finish_reason == "max_output_reached":
            if self.iteration_count < self.max_iterations:
                return True
        
        return False
    
    def build_continuation_prompt(self, 
                                  previous_content: str,
                                  original_prompt: str) -> str:
        """
        Build prompt to continue generation
        
        Args:
            previous_content: Content from previous iteration
            original_prompt: Original task prompt
        
        Returns:
            Continuation prompt
        """
        
        # Trim to first 500 chars to avoid excessive context
        prev_summary = previous_content[:500] + "..." if len(previous_content) > 500 else previous_content
        
        continuation_prompt = (
            f"CONTINUE - Do NOT repeat the previous output.\n"
            f"Previous output: {prev_summary}\n"
            f"Continue from exactly where you left off.\n"
            f"Original task: {original_prompt}\n"
            f"Add the next section without any repetition."
        )
        
        return continuation_prompt
    
    def process_with_continuation(self, 
                                  model: str,
                                  prompt: str,
                                  api_call_func: Callable) -> str:
        """
        Execute API call with automatic continuation handling
        
        Args:
            model: Model to use
            prompt: Initial prompt
            api_call_func: Function that takes (model, prompt) 
                          and returns (content, finish_reason)
        
        Returns:
            Complete assembled content from all iterations
        """
        
        self.accumulated_content = ""
        self.iteration_count = 0
        
        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1
            
            try:
                # Make API call
                content, finish_reason = api_call_func(model, prompt)
                
                # Check for error
                if content == "Error":
                    logger.error(f"API call failed on iteration {self.iteration_count}")
                    break
                
                # Accumulate content
                self.accumulated_content += content
                
                # Check completion
                if not self.should_continue(finish_reason):
                    logger.info(f"Output complete after {self.iteration_count} iteration(s)")
                    break
                
                # Build continuation prompt for next iteration
                prompt = self.build_continuation_prompt(content, prompt)
                logger.info(f"Continuing generation (iteration {self.iteration_count + 1}/{self.max_iterations})")
            
            except Exception as e:
                logger.error(f"Unexpected error during continuation iteration {self.iteration_count}: {e}")
                break
        
        return self.accumulated_content
    
    def reset(self):
        """Reset handler state for reuse"""
        self.accumulated_content = ""
        self.iteration_count = 0


class ContinuationPromptOptimizer:
    """Generate effective continuation prompts with progress tracking"""
    
    @staticmethod
    def create_continuation_prompt(
        previous_content: str,
        original_task: str,
        iteration: int,
        max_iterations: int
    ) -> str:
        """
        Create optimized continuation prompts
        
        Args:
            previous_content: Previously generated content
            original_task: Original task/prompt
            iteration: Current iteration number
            max_iterations: Total expected iterations
        
        Returns:
            Optimized continuation prompt
        """
        
        # Summarize previous content briefly (first 300 chars)
        prev_summary = previous_content[:300] if len(previous_content) <= 300 else previous_content[:300] + "..."
        
        # Progress indicator
        progress = f"{iteration}/{max_iterations}"
        
        # Priority: Avoid repetition
        prompt = (
            f"CONTINUE OUTPUT (Part {progress})\n"
            f"Previous content (last part): {prev_summary}\n"
            f"CRITICAL: Do NOT repeat the previous output. Continue new content only.\n"
            f"Maintain consistency with the previous output.\n"
            f"Original task: {original_task}\n"
            f"Add the next section/items without any repetition of what was already output."
        )
        
        return prompt


class ContinuationMetrics:
    """Track continuation handler performance and effectiveness"""
    
    def __init__(self):
        """Initialize metrics tracker"""
        self.total_calls = 0
        self.continuation_calls = 0
        self.single_turn_calls = 0
        self.success_count = 0
        self.failure_count = 0
        self.iteration_counts = []
        self.total_iterations = 0
    
    def record_completion(self, iteration_count: int, success: bool):
        """
        Record a completion event
        
        Args:
            iteration_count: Number of iterations used
            success: Whether completion was successful
        """
        
        self.total_calls += 1
        self.total_iterations += iteration_count
        
        if iteration_count > 1:
            self.continuation_calls += 1
        else:
            self.single_turn_calls += 1
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self.iteration_counts.append(iteration_count)
    
    def get_report(self) -> dict:
        """
        Generate performance report
        
        Returns:
            Dictionary with performance metrics
        """
        
        if not self.iteration_counts:
            return {}
        
        return {
            "total_completions": self.total_calls,
            "single_turn_completions": self.single_turn_calls,
            "multi_turn_completions": self.continuation_calls,
            "continuation_rate": (
                self.continuation_calls / self.total_calls 
                if self.total_calls > 0 else 0.0
            ),
            "success_rate": (
                self.success_count / self.total_calls
                if self.total_calls > 0 else 0.0
            ),
            "failure_rate": (
                self.failure_count / self.total_calls
                if self.total_calls > 0 else 0.0
            ),
            "avg_iterations": (
                sum(self.iteration_counts) / len(self.iteration_counts)
                if self.iteration_counts else 0.0
            ),
            "max_iterations": max(self.iteration_counts) if self.iteration_counts else 0,
            "min_iterations": min(self.iteration_counts) if self.iteration_counts else 0,
            "total_iterations": self.total_iterations,
        }
    
    def reset(self):
        """Reset metrics for new tracking period"""
        self.total_calls = 0
        self.continuation_calls = 0
        self.single_turn_calls = 0
        self.success_count = 0
        self.failure_count = 0
        self.iteration_counts = []
        self.total_iterations = 0


# Global metrics instance for tracking
_continuation_metrics = ContinuationMetrics()


def get_continuation_metrics() -> ContinuationMetrics:
    """Get global continuation metrics instance"""
    return _continuation_metrics
