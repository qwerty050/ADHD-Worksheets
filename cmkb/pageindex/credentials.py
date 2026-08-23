"""
Credential management system for PageIndex.
Provides provider-agnostic credential handling for OpenAI, Ollama, and future providers.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CredentialProvider(ABC):
    """Abstract credential provider interface"""
    
    @abstractmethod
    def get_credential(self, key_name: str) -> Optional[str]:
        """Get credential value"""
        pass
    
    @abstractmethod
    def set_credential(self, key_name: str, value: str):
        """Set credential value"""
        pass
    
    @abstractmethod
    def has_credential(self, key_name: str) -> bool:
        """Check if credential exists"""
        pass


class EnvironmentCredentialProvider(CredentialProvider):
    """Get credentials from environment variables"""
    
    def __init__(self, env_var_name: str = "CHATGPT_API_KEY"):
        self.env_var_name = env_var_name
    
    def get_credential(self, key_name: str) -> Optional[str]:
        """Get from environment"""
        if key_name == "api_key":
            return os.getenv(self.env_var_name)
        return os.getenv(key_name)
    
    def set_credential(self, key_name: str, value: str):
        """Set in environment (current process only)"""
        os.environ[key_name] = value
        logger.info(f"Set credential {key_name} in environment")
    
    def has_credential(self, key_name: str) -> bool:
        """Check if exists in environment"""
        if key_name == "api_key":
            return self.env_var_name in os.environ
        return key_name in os.environ


class DotenvCredentialProvider(CredentialProvider):
    """Get credentials from .env file"""
    
    def __init__(self, env_file_path: str = ".env"):
        try:
            from dotenv import dotenv_values
            self.env_file_path = env_file_path
            self.env_dict = dotenv_values(env_file_path)
        except ImportError:
            logger.warning("python-dotenv not installed, .env file support disabled")
            self.env_dict = {}
    
    def get_credential(self, key_name: str) -> Optional[str]:
        """Get from .env file"""
        return self.env_dict.get(key_name)
    
    def set_credential(self, key_name: str, value: str):
        """Write to .env file"""
        self.env_dict[key_name] = value
        # Append to file
        with open(self.env_file_path, 'a') as f:
            f.write(f"\n{key_name}={value}")
        logger.info(f"Credential {key_name} written to {self.env_file_path}")
    
    def has_credential(self, key_name: str) -> bool:
        """Check if exists in .env"""
        return key_name in self.env_dict


class HybridCredentialProvider(CredentialProvider):
    """Try multiple providers in order (fallback chain)"""
    
    def __init__(self, providers: list):
        self.providers = providers
    
    def get_credential(self, key_name: str) -> Optional[str]:
        """Try each provider until found"""
        for provider in self.providers:
            try:
                value = provider.get_credential(key_name)
                if value:
                    logger.debug(f"Found credential {key_name} from {provider.__class__.__name__}")
                    return value
            except Exception as e:
                logger.warning(f"Error getting {key_name} from {provider.__class__.__name__}: {e}")
        
        logger.warning(f"Credential {key_name} not found in any provider")
        return None
    
    def set_credential(self, key_name: str, value: str):
        """Set in first provider"""
        if not self.providers:
            raise ValueError("No credential providers configured")
        self.providers[0].set_credential(key_name, value)
    
    def has_credential(self, key_name: str) -> bool:
        """Check any provider"""
        for provider in self.providers:
            try:
                if provider.has_credential(key_name):
                    return True
            except Exception:
                pass
        return False


class CredentialValidator:
    """Validate credential format and functionality"""
    
    @staticmethod
    def is_valid_openai_key(key: str) -> bool:
        """Check if key looks like valid OpenAI key"""
        if not key:
            return False
        if not isinstance(key, str):
            return False
        # OpenAI keys start with "sk-"
        if not key.startswith("sk-"):
            return False
        # Should be ~48 characters
        if len(key) < 40 or len(key) > 100:
            return False
        return True
    
    @staticmethod
    def is_valid_ollama_key(key: Optional[str]) -> bool:
        """Ollama doesn't require API key"""
        return True  # No validation needed


# Initialize default credential system
_env_provider = EnvironmentCredentialProvider(env_var_name="CHATGPT_API_KEY")
_legacy_env_provider = EnvironmentCredentialProvider(env_var_name="Ollama_API_KEY")
_hybrid_provider = HybridCredentialProvider([_env_provider, _legacy_env_provider])


def get_ollama_model() -> Optional[str]:
    """Get Ollama model name from environment"""
    model = os.getenv("OLLAMA_MODEL")
    if not model:
        logger.debug("OLLAMA_MODEL not set, using default model")
    return model


def set_ollama_model(model: str):
    """Set Ollama model in environment"""
    os.environ["OLLAMA_MODEL"] = model
    logger.info(f"Ollama model set to: {model}")


def get_api_key(provider_name: str = "openai") -> Optional[str]:
    """Get API key for specified provider"""
    
    if provider_name == "openai":
        key = os.getenv("CHATGPT_API_KEY") or os.getenv("Ollama_API_KEY")
        
        # Validate key if present
        if key and not CredentialValidator.is_valid_openai_key(key):
            logger.warning("API key doesn't look like valid OpenAI key")
        
        if not key:
            logger.debug(
                "OpenAI API key not found. "
                "Set CHATGPT_API_KEY environment variable or add to .env file"
            )
        
        return key
    
    elif provider_name == "ollama":
        # Ollama doesn't need API key
        return None
    
    else:
        logger.warning(f"Unknown provider: {provider_name}")
        return None


def get_model(provider_name: str = "ollama") -> Optional[str]:
    """Get default model for specified provider"""
    
    if provider_name == "ollama":
        return get_ollama_model()
    
    elif provider_name == "openai":
        # OpenAI model from config, not environment
        return None
    
    else:
        logger.warning(f"Unknown provider: {provider_name}")
        return None


def set_api_key(key: str, provider_name: str = "openai"):
    """Set API key for specified provider"""
    
    if provider_name == "openai":
        if not CredentialValidator.is_valid_openai_key(key):
            raise ValueError("Invalid OpenAI API key format")
        
        _hybrid_provider.set_credential("CHATGPT_API_KEY", key)
        logger.info("OpenAI API key updated")
    
    elif provider_name == "ollama":
        logger.info("Ollama doesn't require API key")
    
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
