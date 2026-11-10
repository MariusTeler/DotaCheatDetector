"""Inject SIMULATED cheat behaviour into a real, parsed match (sensitivity check).

This does not produce a real cheater replay: it edits the extracted data of one
player in memory, then runs the normal analysis so we can see whether each
heuristic reacts. The report title is prefixed with SIMULAT.

Usage:
  python tools/simulate_cheater.py <replay.dem> --pid 3 [--kinds maphack,reaction,script,fogdodge]
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotacheat.analyze import analyze  # noqa: E402
from dotacheat.config import load_config  # noqa: E402
from dotacheat.extract import load_or_parse  # noqa: E402
from dotacheat.heuristics.reaction_time import threat_triggers  # noqa: E402
from dotacheat.model import CombatEvent, MatchData, Order, dist  # noqa: E402
from dotacheat.report import console_summary, write_html, write_json  # noqa: E402


def _order(pid, m, tick, otype, target=0, ability="", x=0.0, y=0.0, ping=40):
    return Order(tick, pid, otype, (m.players[pid].hero_index,), target, 1 if ability else -1,
                 x, y, False, ping, ping + 30, ability)


def inject_maphack(m: MatchData, pid: int, every_s: int = 120) -> int:
    """Attack-click enemy heroes that have been hidden from the team for >= 3 s and are near."""
    me = m.players[pid]
    n, last = 0, -10**9
    for t in range(m.game_start_tick + 300 * 30, m.game_end_tick, 15):
        if t - last < every_s * 30:
            continue
        for e in m.players:
            if e.team == me.team:
                continue
            lv = m.last_visible_tick(e.hero_index, t, me.team)
            if m.visible_to(e.hero_index, t, me.team) == 0 and lv is not None and t - lv > 90 \
                    and dist(m.hero_pos(pid, t), m.hero_pos(e.pid, t)) < 1500:
                m.orders.append(_order(pid, m, t, 4, target=e.hero_index))
                n, last = n + 1, t
                break
    return n


def inject_reactions(m: MatchData, pid: int, delay_ms: float = 60.0) -> int:
    """Answer every threat with BKB exactly ping + delay_ms later (and make it succeed)."""
    n, last = 0, -10**9
    ping = 40
    for t, _desc in threat_triggers(m, pid, 1400.0):
        if t - last < 70 * 30:  # respect a cooldown
            continue
        rt = t + math.ceil((ping + delay_ms) / (1000 / 30))
        m.orders.append(_order(pid, m, rt, 8, ability="item_black_king_bar", ping=ping))
        m.combat.append(CombatEvent(rt, "ITEM", m.players[pid].hero, "", "item_black_king_bar",
                                    False, False, 0, 0.0))
        n, last = n + 1, t
    return n


def inject_script(m: MatchData, pid: int, repeats: int = 6) -> int:
    """The same 4-step combo with identical tick intervals, several times."""
    hero = m.players[pid].hero
    combo = ["item_blink", "item_black_king_bar", "simulated_ultimate", "item_refresher"]
    gaps = [4, 7, 9]
    span = (m.game_end_tick - m.game_start_tick) // (repeats + 1)
    for r in range(repeats):
        t = m.game_start_tick + span * (r + 1)
        for i, a in enumerate(combo):
            m.orders.append(_order(pid, m, t, 8, ability=a))
            m.combat.append(CombatEvent(t + 40, "ITEM", hero, "", a, False, False, 0, 0.0))
            if i < len(gaps):
                t += gaps[i]
    return repeats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("replay", type=Path)
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--kinds", default="maphack,reaction,script")
    ap.add_argument("--cache", type=Path, default=Path("cache/parsed"))
    ap.add_argument("--out", type=Path, default=Path("reports"))
    args = ap.parse_args()
    m = copy.deepcopy(load_or_parse(args.replay, args.cache))
    kinds = set(args.kinds.split(","))
    done = {}
    if "maphack" in kinds:
        done["maphack"] = inject_maphack(m, args.pid)
    if "reaction" in kinds:
        done["reaction"] = inject_reactions(m, args.pid)
    if "script" in kinds:
        done["script"] = inject_script(m, args.pid)
    m.orders.sort(key=lambda o: o.tick)
    m.combat.sort(key=lambda e: e.tick)
    m.source = f"SIMULAT ({', '.join(f'{k}×{v}' for k, v in done.items())} injectat la pid {args.pid}) " + m.source
    r = analyze(m, load_config())
    print(f"injectat pentru {m.players[args.pid].hero_short}: {done}\n")
    print(console_summary(r))
    stem = f"SIMULAT_match_{m.match_id}_pid{args.pid}"
    print("\n", write_html(r, args.out / f"{stem}.html"), write_json(r, args.out / f"{stem}.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
