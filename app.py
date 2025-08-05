# app.py
# FastAPI entrypoint (planner): accepts questions.txt, calls Gemini to plan,
# saves plan to outputs/abdul_breaked_task.txt, invokes executor, returns JSON array.

from __future__ import annotations

import os
import io
import asyncio
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Gemini (google-genai) client
from google import genai

# Executor
from main import run_agent_for_api

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = FastAPI(title="Data Analyst Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).parent.resolve()
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

PLAN_FILE = OUTPUTS / "abdul_breaked_task.txt"

# -----------------------------------------------------------------------------
# Planner (Gemini)
# -----------------------------------------------------------------------------
def _load_planner_prompt() -> str:
    """
    Prefer prompts/abdul_task_breakdown.txt if present; else prompts/task_breakdown.txt.
    """
    p1 = ROOT / "prompts" / "abdul_task_breakdown.txt"
    p2 = ROOT / "prompts" / "task_breakdown.txt"
    for p in (p1, p2):
        if p.exists():
            return p.read_text(encoding="utf-8")
    # Fallback minimal guidance
    return (
        "Break the user question into do-able steps: URLs to fetch, selectors/tables to extract, "
        "computations/plots to perform, and exact output shape (JSON array with base64 image if asked)."
    )


def plan_with_gemini(task_text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    prompt_text = _load_planner_prompt()

    # Compose contents: user task + planning prompt
    resp = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=[task_text, prompt_text],
    )

    plan = (resp.text or "").strip()
    PLAN_FILE.write_text(plan, encoding="utf-8")
    return plan


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY")),
        "has_executor_token": bool(os.getenv("AIPIPE_TOKEN")),
    }


async def _handle_question_upload(file: UploadFile) -> JSONResponse:
    if not file:
        raise HTTPException(status_code=400, detail="File is required")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except Exception:
        # Try latin-1 as fallback
        text = raw.decode("latin-1")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # 1) Plan with Gemini
    plan = plan_with_gemini(text)

    # 2) Execute end-to-end with executor (ChatGPT/tools)
    try:
        final_answer = await asyncio.wait_for(
            run_agent_for_api(text, plan), timeout=170
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timed out while executing the plan")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")

    # 3) Return EXACTLY the JSON array
    return JSONResponse(content=final_answer)


@app.post("/api/")
@app.post("/api/analyze")  # alias for convenience
async def analyze(file: UploadFile = File(...)):
    return await _handle_question_upload(file)


@app.get("/")
def root():
    return {"message": "Data Analyst Agent is running. POST /api/ with questions.txt"}


# -----------------------------------------------------------------------------
# Local dev
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
