"""
Configuration management for PRISM.

Handles persistent configuration including:
- OpenAI API key storage and validation
- Other user preferences

Config is stored in config.json next to the executable/project root.
"""

import json
import os
from pathlib import Path
from typing import Optional

from src.paths import get_config_path


def load_config() -> dict:
    """Load configuration from config.json."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Save configuration to config.json."""
    config_path = get_config_path()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_api_key() -> Optional[str]:
    """
    Get the OpenAI API key.
    
    Priority:
    1. Environment variable OPENAI_API_KEY
    2. Stored in config.json
    """
    # Check environment first
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    
    # Fall back to config file
    config = load_config()
    return config.get("openai_api_key")


def set_api_key(api_key: str) -> None:
    """Save the OpenAI API key to config.json."""
    config = load_config()
    config["openai_api_key"] = api_key
    save_config(config)
    # Also set in environment for current session
    os.environ["OPENAI_API_KEY"] = api_key


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """
    Validate an OpenAI API key without using tokens.
    
    Uses the /models endpoint which is free and returns the list of available models.
    
    Returns:
        (is_valid, message) tuple
    """
    if not api_key:
        return False, "API key is empty"
    
    if not api_key.startswith("sk-"):
        return False, "API key should start with 'sk-'"
    
    # Try to list models - this is a free API call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # List models - this doesn't consume tokens
        models = client.models.list()
        # If we get here, the key is valid
        return True, f"API key is valid. Access to {len(list(models))} models."
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid_api_key" in error_msg.lower():
            return False, "Invalid API key"
        elif "429" in error_msg:
            return False, "Rate limited - but key appears valid"
        else:
            return False, f"Validation error: {error_msg}"


def ensure_api_key_in_env() -> bool:
    """
    Ensure the API key is loaded into the environment.
    
    Returns True if an API key is available, False otherwise.
    """
    api_key = get_api_key()
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        return True
    return False
