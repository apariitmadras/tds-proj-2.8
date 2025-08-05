# app/pipeline.py
# Planner→Executor glue used by the API.
# You can call run_pipeline(task_text) from app.py instead of hand-wiring planning/execution inline.

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from google import genai

from app.settings import get_settings
from main import run_agent_for_api  # executor function provided in main.py


def _load_planner_prompt(prompts_dir: str) -> str:
    """
    Prefer 'prompts/abdul_task_breakdown.txt', else fallback to 'prompts/task_breakdown.txt'.
    Returns a minimal default if neither exists.
    """
    p1 = Path(prompts_dir) / "abdul_task_breakdown.txt"
    p2 = Path(prompts_dir) / "task_breakdown.txt"
    if p1.exists():
        return p1.read_text(encoding="utf-8")
    if p2.exists():
        return p2.read_text(encoding="utf-8")
    return (
        "Break the user question into do-able steps: URLs to fetch, selectors/tables to extract, "
        "computations/plots to perform, and exact output shape (JSON array with base64 image if asked)."
    )


def plan_with_gemini(task_text: str) -> str:
    """
    Calls Gemini with the task + planning prompt and writes the plan to outputs/abdul_breaked_task.txt.
    Returns the plan string.
    """
    st = get_settings()

    if not st.GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")

    client = genai.Client(api_key=st.GEMINI_API_KEY)
    prompt_text = _load_planner_prompt(st.PROMPTS_DIR)

    resp = client.models.generate_content(
        model=st.GEMINI_MODEL,
        contents=[task_text, prompt_text],
    )

    plan = (resp.text or "").strip()
    # Persist plan
    out_path = Path(st.PLAN_FILE)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(plan, encoding="utf-8")
    return plan


async def execute_with_executor(task_text: str, plan_text: str) -> List:
    """
    Delegates to the ChatGPT-based executor (tools) with a timeout.
    Returns the final JSON array (as Python list).
    """
    st = get_settings()
    return await asyncio.wait_for(run_agent_for_api(task_text, plan_text), timeout=st.EXECUTOR_TIMEOUT)


async def run_pipeline(task_text: str) -> List:
    """
    High-level helper: plan → execute → return JSON array.
    Use this from your FastAPI route if you prefer keeping app.py thin.
    """
    plan = plan_with_gemini(task_text)
    result = await execute_with_executor(task_text, plan)
    return result
