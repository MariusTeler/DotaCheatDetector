"""Default locations (cache, reports) — under %LOCALAPPDATA% on Windows."""

from __future__ import annotations

import os
from pathlib import Path


def app_dir() -> Path:
    override = os.environ.get("DOTACHEAT_HOME")
    if override:
        return Path(override)
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "DotaCheatDetector"
    return Path.home() / ".cache" / "dotacheat"


def cache_dir() -> Path:
    return app_dir() / "cache"


def reports_dir() -> Path:
    return app_dir() / "reports"
