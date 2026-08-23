import os
import time
from typing import Protocol, Optional
import requests
from shared.config import OLLAMA_API_URL, ANTHROPIC_API_KEY, LLM_PROVIDER


class LLMClient(Protocol):
    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """
        Generate text from the LLM provider based on the specified model name.
        """
        ...


class OllamaClient:
    def __init__(self):
        self.api_url = OLLAMA_API_URL

    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
        max_retries: int = 3,
        base_delay_s: int = 2,
    ) -> str:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        if as_json:
            payload["format"] = "json"

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(self.api_url, json=payload, timeout=120)
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


class AnthropicClient:
    def __init__(self):
        self.api_key = ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set to use Anthropic.")
            
        self.api_url = "https://api.anthropic.com/v1/messages"

    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
        max_retries: int = 3,
        base_delay_s: int = 2,
    ) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        messages = [{"role": "user", "content": prompt}]
        if as_json:
            # Prefill the assistant's response to guarantee JSON output format
            messages.append({"role": "assistant", "content": "{"})

        payload = {
            "model": model_name,
            "max_tokens": 8192,
            "messages": messages,
        }
        
        if system:
            payload["system"] = system

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
                response.raise_for_status()
                
                content = response.json().get("content", [])
                if content and len(content) > 0:
                    text = content[0].get("text", "")
                    if as_json:
                        return "{" + text
                    return text
                return ""
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    delay = base_delay_s * (2 ** attempt)
                    print(
                        f"Warning: Anthropic request failed. Retrying in {delay}s... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                else:
                    error_text = getattr(e.response, 'text', '') if hasattr(e, 'response') and e.response else ''
                    raise Exception(
                        f"Failed to communicate with Anthropic after {max_retries} "
                        f"retries. Error: {e}\nResponse: {error_text}"
                    )


# --- Singleton Client Factory ---
_client_instance = None

def get_llm_client() -> LLMClient:
    global _client_instance
    if _client_instance is None:
        if LLM_PROVIDER == "anthropic":
            _client_instance = AnthropicClient()
        else:
            _client_instance = OllamaClient()
    return _client_instance
