"""Builders for small synthetic matches used by the unit tests."""

from __future__ import annotations

from dotacheat.model import CombatEvent, MatchData, Order, Player, Track, VisEvent

START = 3000  # game start tick
HEROES = ["axe", "lina", "pudge", "sniper", "zuus", "riki", "lion", "slark", "invoker", "mirana"]


def make_match(minutes: float = 30.0, visibility: bool = True) -> MatchData:
    players = []
    for pid in range(10):
        players.append(Player(pid, 2 if pid < 5 else 3, f"npc_dota_hero_{HEROES[pid]}",
                              f"player{pid}", 1000 + pid, hero_index=100 + pid))
    m = MatchData(
        match_id=1, source="synthetic", game_start_tick=START,
        game_end_tick=START + int(minutes * 60 * 30), players=players, orders=[], combat=[],
        hero_tracks={p.pid: Track() for p in players},
        cursor_tracks={p.pid: Track() for p in players},
        visibility={}, hero_index_by_pid={p.pid: p.hero_index for p in players},
        has_visibility=visibility)
    for p in players:
        set_vis(m, p.pid, 0, radiant=p.team == 2, dire=p.team == 3)
        m.hero_tracks[p.pid].add(0, -6000.0 if p.team == 2 else 6000.0, 0.0)
    return m


def set_vis(m: MatchData, pid: int, tick: int, radiant: bool, dire: bool) -> None:
    p = m.players[pid]
    m.visibility.setdefault(p.hero_index, []).append(
        VisEvent(tick, 1, p.hero, p.team, True, int(radiant), int(dire)))
    m.visibility[p.hero_index].sort(key=lambda e: e.tick)
    m._vis_ticks.pop(p.hero_index, None)


def order(m: MatchData, tick: int, pid: int, order_type: int, target_pid: int | None = None,
          ability: str = "", x: float = 0.0, y: float = 0.0, ping: int = 40, latency: int = 80,
          target_index: int | None = None) -> Order:
    o = Order(tick, pid, order_type, (m.players[pid].hero_index,),
              target_index if target_index is not None else
              (m.players[target_pid].hero_index if target_pid is not None else 0),
              1 if ability else -1, x, y, False, ping, latency, ability)
    m.orders.append(o)
    m.orders.sort(key=lambda o: o.tick)
    return o


def combat(m: MatchData, tick: int, type_: str, attacker: str, target: str, inflictor: str = "",
           value: int = 0, stun: float = 0.0) -> None:
    m.combat.append(CombatEvent(tick, type_, attacker, target, inflictor, False, False, value, stun))
    m.combat.sort(key=lambda e: e.tick)


def move(m: MatchData, pid: int, tick: int, x: float, y: float) -> None:
    m.hero_tracks[pid].add(tick, x, y)
