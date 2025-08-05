# app/schemas.py
# Pydantic models for API responses (kept minimal because request is a file upload).

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    has_gemini_key: bool
    has_executor_token: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class AnalysisResponse(BaseModel):
    """
    Your assignment expects a raw JSON array (e.g., [1, "Titanic", 0.48, "data:image/png;base64,..."]).
    We define a model for documentation only; FastAPI can still return the array directly.
    """
    result: List[Any] = Field(..., description="The final JSON array required by the rubric.")
