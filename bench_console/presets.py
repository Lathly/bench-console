"""Load/save named benchmark presets as JSON files under presets/."""

from __future__ import annotations

import json
from pathlib import Path

from bench_console.config import BenchyConfig, ServerConfig

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"


def list_presets() -> list[str]:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in PRESETS_DIR.glob("*.json"))


def load_preset(name: str) -> tuple[ServerConfig, BenchyConfig]:
    path = PRESETS_DIR / f"{name}.json"
    data = json.loads(path.read_text())
    return ServerConfig.from_dict(data.get("server", {})), BenchyConfig.from_dict(data.get("benchy", {}))


def save_preset(name: str, server: ServerConfig, benchy: BenchyConfig) -> Path:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    path = PRESETS_DIR / f"{name}.json"
    data = {"server": server.to_dict(), "benchy": benchy.to_dict()}
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path
