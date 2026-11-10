"""(d2) Systematic, instant dodges of skillshots (Hook, Arrow, Powershot…).

For every skillshot an enemy (visible to the player's team) aims through the
player, we look for the player's first *sideways* move (relative to the
projectile path) after the cast order, and whether the skillshot missed. Fast
successful dodges are compared with a surrogate baseline (the same player's
orders shifted in time) because high-APM players issue move orders constantly.
"""

from __future__ import annotations

import bisect
import math

from ..gamedata import SKILLSHOTS
from ..model import CAST_ORDERS, MOVE_ORDERS, MatchData, dist
from .base import Heuristic, PlayerFinding, saturate
from .reaction_time import MS_PER_TICK, _seg_dist, poisson_sf


class DodgeHeuristic(Heuristic):
    key = "dodges"
    title = "Eschivări perfecte de skillshot-uri"
    description = ("Skillshot-uri (Hook, Arrow, Powershot…) țintite prin jucător, evitate cu o mișcare "
                   "laterală începută la scurt timp după cast, comparat cu frecvența din întâmplare.")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        c = self.cfg
        fast = float(c.get("fast_ms", 150))
        window = float(c.get("max_window_ms", 900))
        corr = float(c.get("ping_correction", 1.0))
        min_n = int(c.get("min_samples", 4))
        half = float(c.get("fast_share_for_half", 0.5))
        max_p = float(c.get("max_p_value", 0.002))
        combat_ticks = [e.tick for e in match.combat]
        out = {}
        for p in match.players:
            f = PlayerFinding(p.pid, 0.0, "")
            out[p.pid] = f
            if not match.has_visibility:
                f.applicable = False
                f.summary = "fără date de vizibilitate"
                continue
            my_orders = [o for o in match.orders if o.pid == p.pid and p.hero_index in o.units
                         and (o.order_type in MOVE_ORDERS or o.order_type in CAST_ORDERS)]
            my_ticks = [o.tick for o in my_orders]
            threats = n_dodged = 0
            expected = 0.0
            rts = []
            for o in match.orders:
                if o.ability not in SKILLSHOTS or match.team_of(o.pid) == p.team:
                    continue
                speed, rng = SKILLSHOTS[o.ability]
                en = match.hero_pos(o.pid, o.tick)
                me = match.hero_pos(p.pid, o.tick)
                if en is None or me is None:
                    continue
                if match.visible_to(match.players[o.pid].hero_index, o.tick, p.team) != 1:
                    continue
                dx, dy = o.x - en[0], o.y - en[1]
                L = math.hypot(dx, dy) or 1.0
                ux, uy = dx / L, dy / L
                end = (en[0] + ux * rng, en[1] + uy * rng)
                if dist(en, me) > rng or _seg_dist(me, en, end) > 200:
                    continue  # not aimed through the player
                threats += 1
                travel = int((dist(en, me) / speed + 0.6) * 30) + 15
                lo = bisect.bisect_left(combat_ticks, o.tick)
                hi = bisect.bisect_right(combat_ticks, o.tick + travel)
                hit = any(e.attacker == match.players[o.pid].hero and e.target == p.hero
                          and e.inflictor == o.ability for e in match.combat[lo:hi])
                if hit:
                    continue
                n_dodged += 1

                def first_sideways(t0: int, ping: int | None = None):
                    i = bisect.bisect_right(my_ticks, t0)
                    while i < len(my_orders):
                        r = my_orders[i]
                        raw = (r.tick - t0) * MS_PER_TICK
                        if raw > window:
                            return None
                        pos = match.hero_pos(p.pid, r.tick) or me
                        mx, my = r.x - pos[0], r.y - pos[1]
                        m = math.hypot(mx, my)
                        if r.order_type in CAST_ORDERS or (m > 50 and abs(mx * uy - my * ux) / m > 0.5):
                            return r, raw, raw - corr * (ping if ping is not None else r.ping_ms)
                        i += 1
                    return None

                got = first_sideways(o.tick)
                hits = 0
                offsets = [d for d in range(-90, 91, 6) if abs(d) >= 15]
                for d in offsets:
                    g = first_sideways(o.tick + d)
                    hits += bool(g and g[2] < fast and g[2] >= -40)
                expected += hits / len(offsets)
                if got is None:
                    continue
                r, raw, rt = got
                if rt < -40:
                    continue
                rt = max(0.0, rt)
                rts.append(rt)
                if rt < fast:
                    f.detections.append(self.detection(
                        match, p.pid, r.tick, f"eschivare de {o.ability} în {rt:.0f} ms",
                        f"{match.players[o.pid].hero_short} a lansat {o.ability} prin jucător la "
                        f"{match.clock(o.tick)}; jucătorul s-a mișcat lateral după {raw:.0f} ms pe server "
                        f"(~{rt:.0f} ms după scăderea ping-ului {r.ping_ms} ms) și skillshot-ul a ratat.",
                        strength=1.0 - rt / fast, ability=o.ability, raw_ms=round(raw), corrected_ms=round(rt)))
            k = len(f.detections)
            pval = poisson_sf(k, expected)
            f.metrics = {"skillshots_through_player": threats, "dodged": n_dodged, "fast_dodges": k,
                         "expected_fast_by_chance": round(expected, 1), "p_value": round(pval, 4),
                         "reaction_ms": [round(x) for x in rts]}
            if n_dodged >= min_n and k - expected >= 2 and pval <= max_p:
                f.subscore = saturate((k - expected) / n_dodged, half)
            f.summary = (f"{k} eschivări rapide din {n_dodged} skillshot-uri evitate "
                         f"(așteptat din întâmplare ≈{expected:.1f})" if threats else "niciun skillshot prin jucător")
        return out
