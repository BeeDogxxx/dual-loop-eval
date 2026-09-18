"""Shared data models for traces and turns."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    scenario_id: str
    vulnerability_tag: str
    turns: list[Turn] = Field(default_factory=list)
    success: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
