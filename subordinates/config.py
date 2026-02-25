"""Application configuration — loaded from .env / environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _project_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml)."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parent


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
        default="./data/subordinates.db",
        description="SQLite database path (relative to project root)",
    )
    agents_config_path: str = Field(
        default="agents.yaml",
        description="Path to the agent registry YAML (relative to project root)",
    )

    # ── Logging ───────────────────────────────────────────
    log_level: str = Field(default="INFO")

    model_config = {
        "env_file": ".env",
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


# Singleton — import this everywhere
settings = Settings()
