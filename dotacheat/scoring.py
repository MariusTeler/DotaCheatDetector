"""Combine per-heuristic sub-scores into one 0–100 suspicion score per player."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .heuristics.base import PlayerFinding


@dataclass
class PlayerScore:
    pid: int
    score: float                                   # 0..100
    contributions: dict[str, float] = field(default_factory=dict)   # heuristic -> points
    top_reasons: list[str] = field(default_factory=list)


def combine(findings: dict[str, dict[int, PlayerFinding]], weights: dict[str, float],
            titles: dict[str, str] | None = None, top_n: int = 3) -> dict[int, PlayerScore]:
    """Noisy-OR: score = 100 * (1 - prod_h (1 - w_h * s_h)).

    Each heuristic already normalises by event frequency (rates per hour or
    shares of opportunities), so a long match is not more suspicious per se.
    A heuristic's contribution is reported as the points it adds when applied
    in order of strength.
    """
    titles = titles or {}
    pids = sorted({pid for per in findings.values() for pid in per})
    out: dict[int, PlayerScore] = {}
    for pid in pids:
        parts = []
        for key, per in findings.items():
            f = per.get(pid)
            if f is None or not f.applicable:
                continue
            w = float(weights.get(key, 0.5))
            parts.append((max(0.0, min(1.0, w * f.subscore)), key, f))
        parts.sort(key=lambda x: -x[0])
        remaining, score, contrib = 1.0, 0.0, {}
        for p, key, _f in parts:
            gain = 100.0 * remaining * p
            contrib[key] = round(gain, 1)
            score += gain
            remaining *= 1.0 - p
        reasons = [f"{titles.get(key, key)}: {f.summary}" for p, key, f in parts if p >= 0.02][:top_n]
        out[pid] = PlayerScore(pid, round(score, 1), contrib, reasons)
    return out


def band(score: float) -> tuple[str, str]:
    """Human label + css class for a score. Labels describe suspicion, never guilt."""
    if score >= 60:
        return "suspiciune ridicată", "high"
    if score >= 30:
        return "suspiciune moderată", "mid"
    if score >= 10:
        return "suspiciune scăzută", "low"
    return "nimic notabil", "none"


def to_dict(s: PlayerScore) -> dict[str, Any]:
    return {"pid": s.pid, "score": s.score, "contributions": s.contributions,
            "top_reasons": s.top_reasons}
