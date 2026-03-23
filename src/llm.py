"""
Ollama LLM wrapper.

Reads model configuration from environment variables (loaded via .env).
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configuration from .env ---
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

MODELS = {
    "pro":       os.getenv("MODEL_PRO", "gpt-oss:120b-cloud"),
    "flash":     os.getenv("MODEL_FLASH", "gpt-oss:20b-cloud"),
    "flashLite": os.getenv("MODEL_FLASH_LITE", "gpt-oss:20b-cloud"),
}


def call_ollama(
    model: str,
    prompt: str,
    system: str,
    as_json: bool = False,
    max_retries: int = 3,
    base_delay_s: int = 2,
) -> str:
    """Send a prompt to the Ollama API and return the response text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
    }
    if as_json:
        payload["format"] = "json"

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                delay = base_delay_s * (2 ** attempt)
                print(
                    f"Warning: Request failed. Retrying in {delay}s... "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
            else:
                raise Exception(
                    f"Failed to communicate with Ollama after {max_retries} "
                    f"retries. Error: {e}"
                )
