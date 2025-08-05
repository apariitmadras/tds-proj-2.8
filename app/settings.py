# app/settings.py
# Centralized configuration for the service.

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """
    All configuration is read from environment variables.
    Do NOT commit secrets; set them in your hosting provider (e.g., Railway Variables).
    """

    # --- API keys / endpoints ---
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")          # Planner (Gemini)
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")          # Executor (OpenAI)
    OPENAI_BASE: str = os.getenv("OPENAI_BASE", "https://api.openai.com")

    # --- Models ---
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    EXECUTOR_MODEL: str = os.getenv("EXECUTOR_MODEL", "gpt-4o-mini")

    # --- Time budgets (seconds) ---
    # Outer timeout used by the API when waiting on the executor.
    EXECUTOR_TIMEOUT: int = int(os.getenv("EXECUTOR_TIMEOUT", "170"))
    # Inner guard used by the tool-calling loop inside the executor.
    TOOL_LOOP_BUDGET: int = int(os.getenv("TOOL_LOOP_BUDGET", "110"))

    # --- Paths (relative to repo root unless absolute) ---
    OUTPUTS_DIR: str = os.getenv("OUTPUTS_DIR", "outputs")
    PLAN_FILE: str = os.getenv("PLAN_FILE", "outputs/abdul_breaked_task.txt")
    PROMPTS_DIR: str = os.getenv("PROMPTS_DIR", "prompts")

    # --- Misc ---
    ENV: str = os.getenv("ENV", "production")

    # Helpers (optional)
    def require_keys(self) -> None:
        """
        Raise a clear error if required keys are missing.
        Call this early in app startup if you want strict checks.
        """
        missing = []
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached accessor for settings.
    Usage:
        from app.settings import get_settings
        st = get_settings()
        st.require_keys()  # optional strict check
    """
    return Settings()
