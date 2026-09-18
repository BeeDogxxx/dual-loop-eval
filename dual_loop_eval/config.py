"""Settings loaded from environment only (no hardcoded secrets)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration for dual-loop-eval."""

    engine: Literal["heuristic", "deepteam"] = Field(
        default="heuristic",
        description="Attack engine mode",
    )
    artifact_dir: Path = Field(
        default=Path("artifacts"),
        description="Directory for reports and badcase bank",
    )
    judge: Literal["mock", "llm"] = Field(
        default="mock",
        description="Attribution judge mode",
    )
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls) -> "Settings":
        engine = os.environ.get("DLE_ENGINE", "heuristic").lower()
        if engine not in ("heuristic", "deepteam"):
            engine = "heuristic"
        judge = os.environ.get("DLE_JUDGE", "mock").lower()
        if judge not in ("mock", "llm"):
            judge = "mock"
        artifact = os.environ.get("DLE_ARTIFACT_DIR", "artifacts")
        return cls(
            engine=engine,  # type: ignore[arg-type]
            artifact_dir=Path(artifact),
            judge=judge,  # type: ignore[arg-type]
            openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
            openai_base_url=os.environ.get(
                "OPENAI_BASE_URL", "https://api.openai.com/v1"
            ),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )


def get_settings() -> Settings:
    return Settings.from_env()
