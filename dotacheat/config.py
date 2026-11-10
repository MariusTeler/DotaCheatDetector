"""Configuration: packaged defaults (default_config.toml) + optional user overrides."""

from __future__ import annotations

import copy
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def default_config() -> dict[str, Any]:
    text = resources.files("dotacheat").joinpath("default_config.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict[str, Any]:
    cfg = default_config()
    if path:
        with open(path, "rb") as fh:
            cfg = _merge(cfg, tomllib.load(fh))
    if overrides:
        cfg = _merge(cfg, overrides)
    return cfg
