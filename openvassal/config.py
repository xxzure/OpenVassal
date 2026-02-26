"""Application configuration — loaded from .env / environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml)."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parent


_ROOT = _project_root()
_ENV_FILE = str(_ROOT / ".env")


class Settings(BaseSettings):
    """Global settings — populated from environment / .env file."""

    # ── LLM keys ──────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")

    # ── Defaults ──────────────────────────────────────────
    default_model: str = Field(
        default="gpt-4o",
        description="Default LLM model string for agents that don't specify one",
    )

    # ── Paths ─────────────────────────────────────────────
    project_root: Path = Field(default_factory=_project_root)
    database_path: str = Field(
        default="./data/openvassal.db",
        description="SQLite database path (relative to project root)",
    )
    agents_config_path: str = Field(
        default="agents.yaml",
        description="Path to the agent registry YAML (relative to project root)",
    )

    # ── Logging ───────────────────────────────────────────
    log_level: str = Field(default="INFO")

    model_config = {
        "env_file": _ENV_FILE,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    # ── Helpers ───────────────────────────────────────────
    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        if not p.is_absolute():
            p = self.project_root / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def agents_yaml(self) -> Path:
        p = Path(self.agents_config_path)
        if not p.is_absolute():
            p = self.project_root / p
        return p

    def model_post_init(self, __context: object) -> None:
        """Export API keys to os.environ so LiteLLM can discover them."""
        _key_map = {
            "OPENAI_API_KEY": self.openai_api_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "GEMINI_API_KEY": self.gemini_api_key,
        }
        for env_var, value in _key_map.items():
            if value:
                # Use direct set (not setdefault) so reloaded keys take effect
                os.environ[env_var] = value

    def reload(self) -> None:
        """Reload settings from .env file."""
        from dotenv import dotenv_values
        env_path = self.project_root / ".env"
        if env_path.exists():
            vals = dotenv_values(env_path)
            if "DEFAULT_MODEL" in vals:
                self.default_model = vals["DEFAULT_MODEL"] or "gpt-4o"
            if "OPENAI_API_KEY" in vals:
                self.openai_api_key = vals["OPENAI_API_KEY"] or ""
            if "ANTHROPIC_API_KEY" in vals:
                self.anthropic_api_key = vals["ANTHROPIC_API_KEY"] or ""
            if "GEMINI_API_KEY" in vals:
                self.gemini_api_key = vals["GEMINI_API_KEY"] or ""
            # Re-export keys to env
            self.model_post_init(None)
            logger.info("Settings reloaded: default_model=%s", self.default_model)

    def resolve_model(self, model_input: str) -> Any:
        """Resolve a raw model string into the LiteLLM-compatible format or LitellmModel object.
        
        If it's already a litellm/ format or a well-known OpenAI model, return as-is (str).
        Otherwise, scan the custom providers in .env to match the model and
        construct a LitellmModel object with the correct API key and Base URL.
        """
        logger.info("resolve_model called with: %s", model_input)
        
        # If already formatted as litellm/ or a well-known OpenAI model, return as-is
        if model_input.startswith("litellm/") or model_input in ("gpt-4o", "gpt-4o-mini"):
            logger.info("resolve_model: returning as-is (known format): %s", model_input)
            return model_input
        
        # Strip any existing provider prefix to get the bare model name for matching.
        # e.g. "openai/ark-code-latest" -> "ark-code-latest"
        # e.g. "custom_openai/ark-code-latest" -> "ark-code-latest"
        bare_model = model_input
        if "/" in model_input:
            bare_model = model_input.split("/", 1)[1]
        
        # Load env to check custom providers
        from openvassal.web.server import _read_env, _parse_custom_providers
        env = _read_env()
        custom_providers = _parse_custom_providers(env)
        
        for cp in custom_providers:
            # Check if this model (bare name) is listed in this custom provider
            models = [m.strip() for m in cp.get("model", "").split(",")]
            if bare_model in models:
                if cp.get("base_url"):
                    from agents.extensions.models.litellm_model import LitellmModel
                    # LitellmModel calls litellm.acompletion() with explicit api_key
                    # and base_url, so litellm will use these directly and route
                    # through the OpenAI-compatible path. The openai/ prefix tells
                    # litellm to treat this as an OpenAI-compatible API.
                    logger.info("resolve_model: matched custom provider '%s' -> LitellmModel(openai/%s, base_url=%s)", cp['name'], bare_model, cp.get('base_url'))
                    return LitellmModel(
                        model=f"openai/{bare_model}",
                        base_url=cp.get("base_url"),
                        api_key=cp.get("api_key", ""),
                    )
                else:
                    # Provide without base_url, let litellm handle it natively
                    # Litellm needs the api key in env var for native providers
                    provider_name = cp["name"].lower().replace(" ", "_")
                    prefix = provider_name.upper()
                    if cp.get("api_key"):
                        os.environ[f"{prefix}_API_KEY"] = cp["api_key"]
                    result = f"{provider_name}/{bare_model}"
                    logger.info("resolve_model: matched custom provider '%s' -> %s", cp['name'], result)
                    return result
                
        # If not found in custom providers, return as-is (might be native or fail later)
        logger.info("resolve_model: no custom provider match, returning as-is: %s", model_input)
        return model_input


# Singleton — import this everywhere
settings = Settings()
logger.info("Settings loaded: default_model=%s, env_file=%s", settings.default_model, _ENV_FILE)
