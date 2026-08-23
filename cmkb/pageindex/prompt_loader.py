"""
Prompt loader for PageIndex - loads prompts from .txt files
Ensures consistent, schema-enforcing prompts across all operations
"""

from pathlib import Path
import os
import json


PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_REGISTRY_PATH = PROMPTS_DIR / "prompt_registry.json"


def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt from the prompts directory
    
    Args:
        prompt_name: Name of the prompt file (without .txt extension)
        
    Returns:
        The prompt template content
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
    
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt '{prompt_name}' not found at {prompt_path}\n"
            f"Available prompts: {[p.stem for p in PROMPTS_DIR.glob('*.txt')]}"
        )
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def format_prompt(prompt_name: str, **kwargs) -> str:
    """
    Load a prompt and format it with variables using safe substitution.
    Uses string replacement instead of .format() to avoid issues with
    JSON content that contains curly braces.
    
    Args:
        prompt_name: Name of the prompt file
        **kwargs: Variables to format into the prompt
        
    Returns:
        Formatted prompt string
    """
    template = load_prompt(prompt_name)
    
    # Use safe replacements to avoid placeholder interpretation issues
    # Replace {variable_name} with values, but be careful with curly braces in values
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        # Convert value to string if it isn't already
        str_value = str(value)
        result = result.replace(placeholder, str_value)
    
    return result


def load_prompt_registry() -> dict:
    """
    Load prompt registry metadata JSON.

    Returns:
        dict: Registry content with prompt use-case mappings.
    """
    if not PROMPT_REGISTRY_PATH.exists():
        return {"version": "1.0", "prompts": {}}

    with open(PROMPT_REGISTRY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_prompt_by_use_case(use_case: str) -> str:
    """
    Load prompt template via registry use-case key.

    Args:
        use_case: Registry key for prompt (e.g. "toc.detect_single_page")

    Returns:
        str: Prompt template content

    Raises:
        KeyError: If use case not found
        FileNotFoundError: If mapped prompt file does not exist
    """
    registry = load_prompt_registry()
    prompts = registry.get("prompts", {})

    if use_case not in prompts:
        raise KeyError(
            f"Use case '{use_case}' not found in prompt registry at {PROMPT_REGISTRY_PATH}"
        )

    prompt_file = prompts[use_case].get("file")
    if not prompt_file:
        raise KeyError(f"Prompt entry for '{use_case}' is missing 'file' field")

    prompt_path = PROMPTS_DIR / prompt_file
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file for '{use_case}' not found at {prompt_path}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def format_prompt_by_use_case(use_case: str, **kwargs) -> str:
    """
    Format prompt template loaded via registry use-case key.

    Uses safe string replacement rather than str.format to avoid
    accidental interpretation of JSON braces.
    """
    template = load_prompt_by_use_case(use_case)
    result = template

    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))

    return result
