# main.py
# Executor (ChatGPT/tools): runs the plan → scraping → extraction → code execution.
# Exposes: run_agent_for_api(task: str, plan: str = "") -> list

from __future__ import annotations

import os
import sys
import json
import time
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
ROOT = Path(__file__).parent.resolve()
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

GPT_RESP_PATH = OUTPUTS / "gpt_response.json"
SCRAPED_HTML_DEFAULT = OUTPUTS / "scraped_content.html"
TEMP_SCRIPT_PATH = OUTPUTS / "temp_script.py"

# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------
async def scrape_website(url: str, output_file: str = str(SCRAPED_HTML_DEFAULT)) -> Dict[str, Any]:
    """
    Scrape the given URL using Playwright (Chromium) and save HTML to output_file.
    Returns a small JSON payload confirming the write.
    """
    # Most containers (Railway) need these flags
    launch_args = ["--no-sandbox", "--disable-setuid-sandbox"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            content = await page.content()
            out_path = Path(output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            return {"ok": True, "file": str(out_path), "url": url}
        finally:
            await browser.close()


def get_relevant_data(file_name: str, js_selector: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract text from a saved HTML file using a CSS selector (if provided).
    Returns a JSON-serializable dict.
    """
    html = Path(file_name).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    if js_selector:
        elements = soup.select(js_selector)
        return {
            "data": [el.get_text(strip=True) for el in elements],
            "count": len(elements),
            "selector": js_selector,
        }

    # Fallback: entire page text
    return {"data": soup.get_text(separator=" ", strip=True)}


async def answer_questions(code: str) -> str:
    """
    Write provided Python code and run it. The code MUST print ONLY the final JSON array.
    Returns stdout from the script (should be a JSON array string).
    """
    TEMP_SCRIPT_PATH.write_text(code, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(TEMP_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env={**os.environ},  # inherit env
    )

    if proc.returncode != 0 and not proc.stdout.strip():
        # Return a JSON error string so the model can see it as tool output
        return json.dumps({"error": "code_failed", "stderr": proc.stderr})

    return proc.stdout


# Tool schema shared with the model
tools: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "scrape_website",
            "description": "Scrapes a website and saves the HTML to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                    "output_file": {"type": "string", "description": "Path to save HTML (e.g., outputs/scraped_content.html)"},
                },
                "required": ["url", "output_file"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_relevant_data",
            "description": "Extracts relevant text from a saved HTML file using a CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "HTML file path"},
                    "js_selector": {"type": "string", "description": "CSS selector for elements to extract"},
                },
                "required": ["file_name", "js_selector"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_questions",
            "description": "Runs provided Python code that computes the final answers/plot and prints ONLY the JSON array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Standalone Python code that prints the final JSON array."}
                },
                "required": ["code"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]

# -----------------------------------------------------------------------------
# Orchestration helpers
# -----------------------------------------------------------------------------
def _system_prompt() -> str:
    # If you keep prompts/output_contract.txt, you could append it here.
    return (
        "You are an execution agent. Use tools to: (1) fetch the target page, "
        "(2) extract the necessary data, (3) when ready, generate complete Python code and call "
        "'answer_questions' with it. The code MUST print ONLY the final JSON array required by the task, "
        "e.g., [1, \"Titanic\", 0.485782, \"data:image/png;base64,...\"]. "
        "Do not include explanations in the final assistant message—return only the JSON array."
    )


def _chat(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Single chat turn to an OpenAI-compatible endpoint with tools enabled.
    Returns the assistant message object.
    """
    url = "https://aipipe.org/openai/v1/chat/completions"
    token = os.getenv("AIPIPE_TOKEN")
    if not token:
        raise RuntimeError("Missing AIPIPE_TOKEN environment variable")

    with httpx.Client(timeout=120) as client:
        r = client.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": messages, "tools": tools, "tool_choice": "auto"},
        )
        r.raise_for_status()
        data = r.json()

    # Save raw for debugging
    try:
        GPT_RESP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return data["choices"][0]["message"]


def _parse_args(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


async def _call_tool(name: str, args: Dict[str, Any]) -> str:
    if name == "scrape_website":
        res = await scrape_website(**args)
        return json.dumps(res)
    if name == "get_relevant_data":
        res = get_relevant_data(**args)
        return json.dumps(res)
    if name == "answer_questions":
        return await answer_questions(**args)
    return json.dumps({"ok": False, "error": f"Unknown tool '{name}'"})


# -----------------------------------------------------------------------------
# Public entry for API
# -----------------------------------------------------------------------------
async def run_agent_for_api(task: str, plan: str = "") -> list:
    """
    Run the end-to-end flow for a single task.
    Returns the FINAL JSON array as a Python list.
    Raises on timeout or invalid final JSON.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": f"{task}\n\nPlan:\n{plan}\n\nUse the tools. When done, return ONLY the final JSON array.",
        },
    ]

    start = time.time()
    while True:
        if time.time() - start > 110:  # safety budget for the tool loop; API has its own outer timeout
            raise TimeoutError("Tool loop exceeded time budget")

        msg = _chat(messages)
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            final_text = (msg.get("content") or "").strip()
            try:
                parsed = json.loads(final_text)
                if not isinstance(parsed, list):
                    raise ValueError("Final content is JSON but not a list")
                return parsed
            except json.JSONDecodeError as e:
                raise ValueError(f"Final assistant content was not valid JSON: {e}")

        messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            args = _parse_args(tc["function"].get("arguments"))
            out = await _call_tool(fn_name, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": fn_name, "content": out})


# -----------------------------------------------------------------------------
# Optional CLI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the execution agent locally.")
    parser.add_argument("task", type=str, help="User task/question")
    parser.add_argument("--plan", type=str, default=os.getenv("PLAN", ""), help="Optional pre-generated plan")
    args = parser.parse_args()

    result = asyncio.run(run_agent_for_api(args.task, args.plan))
    print(json.dumps(result, ensure_ascii=False))
