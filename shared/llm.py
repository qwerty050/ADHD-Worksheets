import json
import time
from typing import Protocol, Optional, Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from shared.config import (
    OLLAMA_API_URL,
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    ANTHROPIC_MAX_TOKENS,
    LLM_PROVIDER,
)


class LLMPipelineError(Exception):
    """Raised when the LLM cannot be reached or its output fails validation."""


class LLMClient(Protocol):
    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from the LLM provider based on the specified model name."""
        ...


def _retry_loop(fn, max_retries: int, base_delay_s: int, label: str):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < max_retries:
                delay = base_delay_s * (2 ** attempt)
                print(
                    f"Warning: {label} request failed. Retrying in {delay}s... "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
    error_text = ""
    response = getattr(last_exc, "response", None)
    if response is not None:
        error_text = getattr(response, "text", "")[:500]
    raise LLMPipelineError(f"Failed to communicate with {label} after {max_retries} retries. Error: {last_exc}\nResponse: {error_text}")


class OllamaClient:
    def __init__(self):
        self.api_url = OLLAMA_API_URL

    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
        max_tokens: Optional[int] = None,
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
        if max_tokens:
            payload["options"] = {"num_predict": max_tokens}

        def call():
            response = requests.post(self.api_url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json().get("response", "")

        return _retry_loop(call, max_retries, base_delay_s, "Ollama")


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
        max_tokens: Optional[int] = None,
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
            "max_tokens": max_tokens or ANTHROPIC_MAX_TOKENS,
            "messages": messages,
        }

        if system:
            payload["system"] = system

        def call():
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            if data.get("stop_reason") == "max_tokens":
                raise LLMPipelineError(
                    f"Anthropic output truncated at max_tokens={payload['max_tokens']} "
                    f"for model {model_name}. Raise ANTHROPIC_MAX_TOKENS or shrink the input."
                )
            content = data.get("content", [])
            if content and len(content) > 0:
                text = content[0].get("text", "")
                if as_json:
                    return "{" + text
                return text
            return ""

        return _retry_loop(call, max_retries, base_delay_s, "Anthropic")


class OpenAIClient:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set to use OpenAI.")

        self.api_url = "https://api.openai.com/v1/chat/completions"

    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        base_delay_s: int = 2,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model_name, "messages": messages}
        if as_json:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        def call():
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            choices = response.json().get("choices", [])
            if not choices:
                return ""
            finish = choices[0].get("finish_reason")
            if finish == "length":
                raise LLMPipelineError(
                    f"OpenAI output truncated (finish_reason=length) for model {model_name}. "
                    "Raise max_tokens or shrink the input."
                )
            return choices[0].get("message", {}).get("content", "") or ""

        return _retry_loop(call, max_retries, base_delay_s, "OpenAI")


class GeminiClient:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set to use Gemini.")

        self.api_base = "https://generativelanguage.googleapis.com/v1beta/models"

    def generate(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        as_json: bool = False,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        base_delay_s: int = 2,
    ) -> str:
        url = f"{self.api_base}/{model_name}:generateContent?key={self.api_key}"

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        generation_config = {}
        if as_json:
            generation_config["responseMimeType"] = "application/json"
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens
        if generation_config:
            payload["generationConfig"] = generation_config

        def call():
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            candidates = response.json().get("candidates", [])
            if not candidates:
                return ""
            finish = candidates[0].get("finishReason")
            if finish == "MAX_TOKENS":
                raise LLMPipelineError(
                    f"Gemini output truncated (finishReason=MAX_TOKENS) for model {model_name}. "
                    "Raise max_tokens or shrink the input."
                )
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)

        return _retry_loop(call, max_retries, base_delay_s, "Gemini")


_CLIENT_CLASSES = {
    "ollama": OllamaClient,
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "gemini": GeminiClient,
}

# --- Singleton Client Factory ---
_client_instance = None


def get_llm_client() -> LLMClient:
    global _client_instance
    if _client_instance is None:
        client_cls = _CLIENT_CLASSES.get(LLM_PROVIDER)
        if client_cls is None:
            raise ValueError(
                f"Unknown LLM_PROVIDER {LLM_PROVIDER!r}. Supported providers: {sorted(_CLIENT_CLASSES)}"
            )
        _client_instance = client_cls()
    return _client_instance


T = TypeVar("T", bound=BaseModel)


def generate_json(
    prompt: str,
    model_name: str,
    system: Optional[str],
    response_model: Type[T],
    max_tokens: Optional[int] = None,
    max_repair_retries: int = 2,
) -> T:
    """
    Generate JSON and validate it against a pydantic model. Parse/validation
    errors are fed back to the model for a bounded number of repair attempts;
    persistent failure raises LLMPipelineError instead of silently degrading.
    """
    client = get_llm_client()
    user_prompt = prompt
    last_error: Optional[Exception] = None

    for _ in range(max_repair_retries + 1):
        raw = client.generate(
            prompt=user_prompt,
            model_name=model_name,
            system=system,
            as_json=True,
            max_tokens=max_tokens,
        )
        try:
            data = json.loads(raw)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            user_prompt = (
                f"{prompt}\n\n"
                f"Your previous response was invalid: {str(e)[:2000]}\n"
                f"Return the corrected response as valid JSON only. No preamble or commentary."
            )

    raise LLMPipelineError(f"LLM output failed validation after repair retries: {last_error}")
