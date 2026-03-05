"""Application configuration — loaded from .env / environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path

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


def _safe_env_file() -> str | None:
    """Return .env path only if it's accessible (avoids macOS sandbox PermissionError)."""
    env_path = _ROOT / ".env"
    try:
        if env_path.is_file():
            return str(env_path)
    except (PermissionError, OSError):
        logger.debug("Cannot access .env file — using environment variables only")
    return None


_ENV_FILE = _safe_env_file()


class Settings(BaseSettings):
    """Global settings — populated from environment / .env file."""

    # ── LLM keys ──────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    moonshot_api_key: str = Field(default="", description="Moonshot (Kimi) API key")

    # ── Defaults ──────────────────────────────────────────
    default_agent: str = Field(
        default="",
        description="Default agent name to use when none is specified",
    )

    # ── mem0 ──────────────────────────────────────────────
    mem0_user_id: str = Field(
        default="default_user",
        description="User ID for mem0 memory isolation",
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
        """Export API keys to os.environ so CrewAI/LiteLLM can discover them."""
        _key_map = {
            "OPENAI_API_KEY": self.openai_api_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "GEMINI_API_KEY": self.gemini_api_key,
            "MOONSHOT_API_KEY": self.moonshot_api_key,
        }
        for env_var, value in _key_map.items():
            if value:
                os.environ[env_var] = value

    def reload(self) -> None:
        """Reload settings from .env file."""
        from dotenv import dotenv_values

        env_path = self.project_root / ".env"
        try:
            if not env_path.exists():
                return
        except (PermissionError, OSError):
            logger.debug("Cannot access .env for reload")
            return
        vals = dotenv_values(env_path)
        for attr, env_key in [
            ("openai_api_key", "OPENAI_API_KEY"),
            ("anthropic_api_key", "ANTHROPIC_API_KEY"),
            ("gemini_api_key", "GEMINI_API_KEY"),
            ("moonshot_api_key", "MOONSHOT_API_KEY"),
            ("default_agent", "DEFAULT_AGENT"),
            ("mem0_user_id", "MEM0_USER_ID"),
        ]:
            if env_key in vals:
                setattr(self, attr, vals[env_key] or getattr(self, attr))
        # Re-export keys to env
        self.model_post_init(None)
        logger.info("Settings reloaded")


# Singleton — import this everywhere
settings = Settings()
logger.info("Settings loaded: env_file=%s", _ENV_FILE or "(env vars only)")

