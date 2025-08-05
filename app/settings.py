# app/settings.py
# Centralized configuration for the service.

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    # API keys / endpoints
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    AIPIPE_TOKEN: str | None = os.getenv("AIPIPE_TOKEN")  # token for OpenAI-compatible endpoint used in main.py

    # Models
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    EXECUTOR_MODEL: str = os.getenv("EXECUTOR_MODEL", "gpt-4o-mini")  # for reference/logs

    # Time budgets (seconds)
    EXECUTOR_TIMEOUT: int = int(os.getenv("EXECUTOR_TIMEOUT", "170"))  # outer API timeout
    TOOL_LOOP_BUDGET: int = int(os.getenv("TOOL_LOOP_BUDGET", "110"))  # inner loop guard (also set in main.py)

    # Paths
    OUTPUTS_DIR: str = os.getenv("OUTPUTS_DIR", "outputs")
    PLAN_FILE: str = os.getenv("PLAN_FILE", "outputs/abdul_breaked_task.txt")
    PROMPTS_DIR: str = os.getenv("PROMPTS_DIR", "prompts")

    # Misc
    ENV: str = os.getenv("ENV", "production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
