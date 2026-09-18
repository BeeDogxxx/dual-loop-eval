"""Load gold / error / challenge JSONL dual-loop assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

AssetKind = Literal["gold", "error", "challenge"]

# Prefer packaged data next to this module; fall back to repo assets/data
_PKG_DATA = Path(__file__).resolve().parent / "data"
_REPO_DATA = Path(__file__).resolve().parents[2] / "assets" / "data"


def _data_dir() -> Path:
    if (_PKG_DATA / "gold.jsonl").exists():
        return _PKG_DATA
    return _REPO_DATA


def load_asset_set(kind: AssetKind, data_dir: Path | None = None) -> list[dict[str, Any]]:
    root = data_dir or _data_dir()
    path = root / f"{kind}.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_all_assets(data_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    return {
        "gold": load_asset_set("gold", data_dir),
        "error": load_asset_set("error", data_dir),
        "challenge": load_asset_set("challenge", data_dir),
    }
