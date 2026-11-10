"""Plain data model extracted once from a replay and shared by all heuristics.

Everything here is pickle-able so a parsed match can be cached on disk and the
heuristics re-run (e.g. with different thresholds) without re-parsing.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from . import TICKS_PER_SECOND

RADIANT, DIRE = 2, 3

# dotaunitorder_t values used by the heuristics
ORDER_MOVE_TO_POSITION = 1
ORDER_MOVE_TO_TARGET = 2
ORDER_ATTACK_MOVE = 3
ORDER_ATTACK_TARGET = 4
ORDER_CAST_POSITION = 5
ORDER_CAST_TARGET = 6
ORDER_CAST_TARGET_TREE = 7
ORDER_CAST_NO_TARGET = 8
ORDER_CAST_TOGGLE = 9
ORDER_HOLD_POSITION = 10
ORDER_STOP = 21
ORDER_MOVE_TO_DIRECTION = 28
ORDER_VECTOR_TARGET_POSITION = 30

CAST_ORDERS = frozenset({ORDER_CAST_POSITION, ORDER_CAST_TARGET, ORDER_CAST_TARGET_TREE,
                         ORDER_CAST_NO_TARGET, ORDER_CAST_TOGGLE, ORDER_VECTOR_TARGET_POSITION})
UNIT_TARGET_ORDERS = frozenset({ORDER_MOVE_TO_TARGET, ORDER_ATTACK_TARGET, ORDER_CAST_TARGET})
MOVE_ORDERS = frozenset({ORDER_MOVE_TO_POSITION, ORDER_MOVE_TO_TARGET, ORDER_ATTACK_MOVE,
                         ORDER_MOVE_TO_DIRECTION})


@dataclass(slots=True)
class Player:
    pid: int
    team: int
    hero: str            # npc name, e.g. npc_dota_hero_axe
    name: str            # Steam persona name
    account_id: int
    hero_index: int = -1  # entity index of the player's (canonical) hero

    @property
    def hero_short(self) -> str:
        return self.hero.replace("npc_dota_hero_", "")


@dataclass(slots=True)
class Order:
    tick: int
    pid: int
    order_type: int
    units: tuple[int, ...]
    target_index: int
    ability_index: int
    x: float
    y: float
    queue: bool
    ping_ms: int
    latency_ms: int
    ability: str = ""     # resolved ability / item name ("" when not a cast)


@dataclass(slots=True)
class CombatEvent:
    tick: int
    type: str             # DAMAGE, MODIFIER_ADD, DEATH, ABILITY, ITEM, ...
    attacker: str
    target: str
    inflictor: str
    attacker_illusion: bool
    target_illusion: bool
    value: int
    stun_duration: float


@dataclass(slots=True)
class VisEvent:
    tick: int
    serial: int
    name: str
    team: int | None
    active: bool
    radiant: int          # 1 visible, 0 hidden, -1 unknown
    dire: int


class Track:
    """Change-only time series of 2-D points (hero positions, cursor)."""

    __slots__ = ("ticks", "xs", "ys")

    def __init__(self) -> None:
        self.ticks: list[int] = []
        self.xs: list[float] = []
        self.ys: list[float] = []

    def add(self, tick: int, x: float, y: float) -> None:
        if self.ticks and self.xs[-1] == x and self.ys[-1] == y:
            return
        if self.ticks and self.ticks[-1] == tick:
            self.xs[-1], self.ys[-1] = x, y
            return
        self.ticks.append(tick)
        self.xs.append(x)
        self.ys.append(y)

    def at(self, tick: int) -> tuple[float, float] | None:
        i = bisect.bisect_right(self.ticks, tick) - 1
        if i < 0:
            return None
        return self.xs[i], self.ys[i]

    def __len__(self) -> int:
        return len(self.ticks)


def dist(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return math.inf
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class MatchData:
    match_id: int
    source: str
    game_start_tick: int
    game_end_tick: int
    players: list[Player]
    orders: list[Order]
    combat: list[CombatEvent]
    hero_tracks: dict[int, Track]                 # pid -> hero position
    cursor_tracks: dict[int, Track]               # pid -> raw m_iCursor values
    visibility: dict[int, list[VisEvent]]         # entity index -> events
    hero_index_by_pid: dict[int, int]
    illusion_indices: set[int] = field(default_factory=set)
    pauses: list[tuple[int, int | None]] = field(default_factory=list)
    has_visibility: bool = True
    parser_version: str = ""
    _vis_ticks: dict[int, list[int]] = field(default_factory=dict, repr=False)

    # ---- time helpers -------------------------------------------------
    def paused_ticks_before(self, tick: int) -> int:
        total = 0
        for start, end in self.pauses:
            if start >= tick:
                break
            stop = tick if end is None else min(end, tick)
            total += max(0, stop - start)
        return total

    def game_time(self, tick: int) -> float:
        """Seconds since the horn (pause aware, negative before it)."""
        return (tick - self.game_start_tick - (self.paused_ticks_before(tick)
                - self.paused_ticks_before(self.game_start_tick))) / TICKS_PER_SECOND

    def clock(self, tick: int) -> str:
        t = self.game_time(tick)
        sign = "-" if t < 0 else ""
        t = abs(int(t))
        return f"{sign}{t // 60:02d}:{t % 60:02d}"

    @property
    def duration_s(self) -> float:
        return max(1.0, self.game_time(self.game_end_tick))

    # ---- lookups ------------------------------------------------------
    def player(self, pid: int) -> Player:
        return self.players[pid]

    def team_of(self, pid: int) -> int:
        return self.players[pid].team

    def pid_by_hero(self) -> dict[str, int]:
        return {p.hero: p.pid for p in self.players}

    def vis_event(self, index: int, tick: int) -> VisEvent | None:
        evs = self.visibility.get(index)
        if not evs:
            return None
        ticks = self._vis_ticks.get(index)
        if ticks is None:
            ticks = self._vis_ticks[index] = [e.tick for e in evs]
        i = bisect.bisect_right(ticks, tick) - 1
        return evs[i] if i >= 0 else None

    def visible_to(self, index: int, tick: int, team: int) -> int:
        """1 visible, 0 hidden, -1 unknown — visibility of entity *index* to *team*."""
        e = self.vis_event(index, tick)
        if e is None or not e.active:
            return -1
        return e.radiant if team == RADIANT else e.dire

    def last_visible_tick(self, index: int, tick: int, team: int) -> int | None:
        """Last tick <= *tick* at which *index* was visible to *team* (None if never)."""
        evs = self.visibility.get(index)
        if not evs:
            return None
        self.vis_event(index, tick)  # ensure tick cache
        ticks = self._vis_ticks[index]
        i = bisect.bisect_right(ticks, tick) - 1
        while i >= 0:
            e = evs[i]
            state = e.radiant if team == RADIANT else e.dire
            if state == 1:
                # visible from e.tick until the next event
                nxt = ticks[i + 1] if i + 1 < len(ticks) else tick
                return min(tick, nxt)
            i -= 1
        return None

    def hero_pos(self, pid: int, tick: int) -> tuple[float, float] | None:
        tr = self.hero_tracks.get(pid)
        return tr.at(tick) if tr else None
