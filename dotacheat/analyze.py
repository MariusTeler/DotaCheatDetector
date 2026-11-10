"""Run every enabled heuristic on a match and assemble the result."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import __version__
from .heuristics.base import PlayerFinding
from .heuristics.registry import all_heuristics
from .model import MatchData
from .scoring import PlayerScore, combine


@dataclass
class AnalysisResult:
    match: MatchData
    findings: dict[str, dict[int, PlayerFinding]]
    scores: dict[int, PlayerScore]
    heuristics: list[dict[str, str]]
    config: dict[str, Any]
    generated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    version: str = __version__


def analyze(match: MatchData, cfg: dict[str, Any]) -> AnalysisResult:
    findings: dict[str, dict[int, PlayerFinding]] = {}
    meta = []
    for H in all_heuristics():
        h = H(cfg)
        if not h.enabled:
            continue
        findings[h.key] = h.run(match)
        for per in findings[h.key].values():
            per.detections.sort(key=lambda d: d.tick)
        meta.append({"key": h.key, "title": h.title, "description": h.description})
    titles = {m["key"]: m["title"] for m in meta}
    scores = combine(findings, cfg.get("scoring", {}).get("weights", {}), titles)
    return AnalysisResult(match, findings, scores, meta, cfg)
