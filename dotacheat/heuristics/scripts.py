"""(c) Scripts / auto-combos: machine-like timing in repeated cast sequences.

Humans repeating a combo (e.g. Blink → Ravage → Refresher) vary by a few ticks
(1 tick = 33 ms) each time. Scripts replay the same delays, so the same
sequence shows the *same tick intervals* over and over. A second, independent
signal: several *different* abilities/items ordered within the same tick.
"""

from __future__ import annotations

import fnmatch
import statistics
from collections import defaultdict

from ..model import CAST_ORDERS, MatchData
from .base import Heuristic, PlayerFinding, saturate
from .reaction_time import successful_casts


def _chained(done: dict[str, list[int]], prev_ability: str, tick: int, tol: int = 2) -> bool:
    """True if *tick* coincides with the completion of *prev_ability*'s cast: the order
    was buffered by the engine during the cast point, so its timing is the game's, not the player's."""
    import bisect

    ticks = done.get(prev_ability, [])
    i = bisect.bisect_left(ticks, tick - tol)
    return i < len(ticks) and ticks[i] <= tick + tol


def _ignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


class ScriptHeuristic(Heuristic):
    key = "scripts"
    title = "Scripturi / auto-combo"
    description = ("Secvențe de abilități/iteme repetate cu intervale identice la nivel de tick "
                   "(variație anormal de mică) și mai multe abilități diferite ordonate în același tick.")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        c = self.cfg
        gap = int(float(c.get("burst_gap_s", 0.6)) * 30)
        min_rep = int(c.get("min_repeats", 3))
        max_std = float(c.get("max_std_ticks", 0.5))
        min_mean = float(c.get("min_mean_ticks", 2.0))
        same_tick_n = int(c.get("same_tick_distinct_casts", 3))
        ignore = list(c.get("ignore", []))
        half = float(c.get("incidents_for_half", 3.0))
        hours = match.duration_s / 3600.0

        casts: dict[int, list[tuple[int, str]]] = defaultdict(list)
        for o in match.orders:
            if o.order_type in CAST_ORDERS and o.ability and not _ignored(o.ability, ignore):
                lst = casts[o.pid]
                if lst and lst[-1][1] == o.ability and o.tick - lst[-1][0] < 15:
                    continue  # repeated press of the same key
                lst.append((o.tick, o.ability))

        out = {}
        for p in match.players:
            f = PlayerFinding(p.pid, 0.0, "")
            out[p.pid] = f
            seq = casts.get(p.pid, [])
            done = successful_casts(match, p.pid)
            usable = set(done)
            bursts, cur = [], []
            for t, a in seq:
                if cur and t - cur[-1][0] > gap:
                    bursts.append(cur)
                    cur = []
                cur.append((t, a))
            if cur:
                bursts.append(cur)

            # --- same-tick multi-casts --------------------------------------
            same_tick = 0
            for b in bursts:
                by_tick: dict[int, set[str]] = defaultdict(set)
                for t, a in b:
                    if a in usable:  # only abilities/items this hero really used during the match
                        by_tick[t].add(a)
                for t, names in by_tick.items():
                    if len(names) >= same_tick_n:
                        same_tick += 1
                        f.detections.append(self.detection(
                            match, p.pid, t, f"{len(names)} abilități în același tick",
                            f"{', '.join(sorted(names))} au fost ordonate toate în același tick de server "
                            f"(<33 ms). Un om apasă rar {len(names)} taste diferite atât de sincron.",
                            strength=min(1.0, 0.4 + 0.2 * (len(names) - same_tick_n)),
                            kind="same_tick", abilities=sorted(names)))

            # --- repeated sequences with identical timing ------------------
            occ: dict[tuple[str, ...], list[tuple[int, tuple[int, ...]]]] = defaultdict(list)
            for b in bursts:
                for n in range(3, min(6, len(b)) + 1):
                    for i in range(len(b) - n + 1):
                        w = b[i:i + n]
                        names = tuple(a for _, a in w)
                        if len(set(names)) < 2:
                            continue
                        if any(_chained(done, w[j][1], w[j + 1][0]) for j in range(n - 1)):
                            continue
                        iv = tuple(w[j + 1][0] - w[j][0] for j in range(n - 1))
                        occ[names].append((w[0][0], iv))
            flagged: list[tuple[int, int]] = []  # covered tick ranges
            n_seq = 0
            for names in sorted(occ, key=len, reverse=True):
                runs = []
                for start, iv in sorted(occ[names]):
                    if not runs or start - runs[-1][0] > 60:  # distinct uses >= 2 s apart
                        runs.append((start, iv))
                if len(runs) < min_rep:
                    continue
                cols = list(zip(*(iv for _, iv in runs)))
                means = [statistics.fmean(col) for col in cols]
                stds = [statistics.pstdev(col) for col in cols]
                if max(means) < min_mean or max(stds) > max_std:
                    continue
                spans = [(s, s + sum(iv)) for s, iv in runs]
                if any(a <= y and x <= b for a, b in spans for x, y in flagged):
                    continue  # already reported as part of a longer sequence
                flagged.extend(spans)
                n_seq += 1
                iv_ms = " / ".join(f"{m * 1000 / 30:.0f}" for m in means)
                f.detections.append(self.detection(
                    match, p.pid, runs[0][0], f"combo repetat identic de {len(runs)} ori",
                    f"Secvența {' → '.join(names)} a fost executată de {len(runs)} ori cu aceleași "
                    f"intervale (≈{iv_ms} ms; abatere standard max {max(stds):.2f} tick-uri). "
                    f"Momente: {', '.join(match.clock(s) for s, _ in runs[:8])}. "
                    f"Un om variază de obicei cu câteva tick-uri de la o execuție la alta.",
                    strength=min(1.0, 0.5 + 0.1 * (len(runs) - min_rep)),
                    kind="repeated_sequence", sequence=list(names), repeats=len(runs),
                    mean_intervals_ticks=[round(m, 2) for m in means],
                    std_intervals_ticks=[round(s, 2) for s in stds],
                    occurrences=[match.clock(s) for s, _ in runs]))

            n = len(f.detections)
            rate = n / hours
            f.metrics = {"cast_orders": len(seq), "bursts": len(bursts), "same_tick_multicasts": same_tick,
                         "identical_sequences": n_seq, "incidents_per_hour": round(rate, 2)}
            f.subscore = saturate(rate, half) if n >= 2 else 0.0
            f.summary = (f"{n_seq} combo-uri repetate identic, {same_tick} multi-cast-uri în același tick"
                         if n else "niciun tipar de script")
        return out
