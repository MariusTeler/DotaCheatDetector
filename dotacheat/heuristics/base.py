"""Common types for heuristics."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from ..model import MatchData


@dataclass
class Detection:
    """One suspicious moment, explainable on its own."""

    heuristic: str
    pid: int
    tick: int
    clock: str            # in-game MM:SS, to look it up in the Dota client replay viewer
    title: str            # short label
    explanation: str      # why it is suspicious, in plain language
    strength: float = 1.0  # 0..1, how strong this single moment is
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlayerFinding:
    pid: int
    subscore: float                       # 0..1
    summary: str                          # one line, shown as a "top reason"
    metrics: dict[str, Any] = field(default_factory=dict)
    detections: list[Detection] = field(default_factory=list)
    applicable: bool = True               # False when the data needed is missing

    def to_dict(self) -> dict:
        d = asdict(self)
        d["detections"] = [x.to_dict() for x in self.detections]
        return d


def saturate(x: float, half: float) -> float:
    """Map x >= 0 to [0, 1): 0 -> 0, half -> 0.5, grows smoothly towards 1."""
    if x <= 0 or half <= 0:
        return 0.0
    return 1.0 - math.pow(0.5, x / half)


class Heuristic:
    key = "base"
    title = "base"
    description = ""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg.get(self.key, {})

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", True))

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:  # pragma: no cover
        raise NotImplementedError

    def detection(self, match: MatchData, pid: int, tick: int, title: str, explanation: str,
                  strength: float = 1.0, **data) -> Detection:
        return Detection(self.key, pid, tick, match.clock(tick), title, explanation,
                         round(float(strength), 3), data)

    @staticmethod
    def not_applicable(match: MatchData, reason: str) -> dict[int, PlayerFinding]:
        return {p.pid: PlayerFinding(p.pid, 0.0, reason, applicable=False) for p in match.players}
