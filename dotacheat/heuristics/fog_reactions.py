"""(a2) Reacting to enemies the team cannot see (dodging ganks from the fog).

A "hidden threat" episode: an enemy hero, NOT visible to the player's team (so
not on the minimap either — wards and allied vision are already accounted for
by the visibility bitsets), comes within ``threat_radius`` of the player and is
closing in. We measure how often the player *turns away* from that enemy within
``retreat_window_s`` and compare it with a matched control. The control is the same player with a hidden enemy just as close but NOT
coming at him (enemy's own velocity), so map position, lane habits and fights
cancel out. A large, statistically unlikely lift means the player keeps
reacting to information he should not have.
"""

from __future__ import annotations

import math

from ..model import RADIANT, MatchData, dist
from .base import Heuristic, PlayerFinding, saturate

STEP = 15  # ticks (0.5 s)


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k), X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    p = min(max(p, 1e-9), 1 - 1e-9)
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * p ** i * (1 - p) ** (n - i)
    return min(1.0, total)


class FogReactionsHeuristic(Heuristic):
    key = "fog_reactions"
    title = "Reacții la inamici din ceață"
    description = ("Cât de des jucătorul se întoarce/retrage exact când un erou inamic INVIZIBIL echipei "
                   "lui se apropie, față de cât de des face asta în momente obișnuite.")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        if not match.has_visibility:
            return self.not_applicable(match, "replay-ul nu conține date de vizibilitate")
        c = self.cfg
        radius = float(c.get("threat_radius", 1300))
        approach = float(c.get("approach_speed", 150))
        win = int(float(c.get("retreat_window_s", 1.5)) * 30)
        turn = math.radians(float(c.get("retreat_min_turn_deg", 100)))
        min_n = int(c.get("min_samples", 6))
        lift_half = float(c.get("lift_for_half", 2.5))
        max_p = float(c.get("max_p_value", 0.002))
        start, end = match.game_start_tick + 60 * 30, match.game_end_tick - win - STEP

        def moving(pid: int, t: int) -> bool:
            a, b = match.hero_pos(pid, t - 150), match.hero_pos(pid, t)
            return a is not None and b is not None and dist(a, b) > 1

        def turned_away(pid: int, t: int, threat_xy) -> bool:
            p0, p1, p2 = match.hero_pos(pid, t - STEP), match.hero_pos(pid, t), match.hero_pos(pid, t + win)
            if p0 is None or p1 is None or p2 is None:
                return False
            v0 = (p1[0] - p0[0], p1[1] - p0[1])
            v1 = (p2[0] - p1[0], p2[1] - p1[1])
            n1 = math.hypot(*v1)
            if n1 < 150:
                return False
            away = (p1[0] - threat_xy[0], p1[1] - threat_xy[1])
            na = math.hypot(*away) or 1.0
            if (v1[0] * away[0] + v1[1] * away[1]) / (n1 * na) < 0.5:
                return False  # not moving away from the threat afterwards
            n0 = math.hypot(*v0)
            if n0 < 20:
                return True  # was standing, now walks away
            cosang = (v0[0] * v1[0] + v0[1] * v1[1]) / (n0 * n1)
            return math.acos(max(-1.0, min(1.0, cosang))) >= turn

        out = {}
        for p in match.players:
            f = PlayerFinding(p.pid, 0.0, "")
            out[p.pid] = f
            enemies = [e for e in match.players if e.team != p.team]
            episodes = retreats = 0
            base_n = base_k = 0
            cooldown: dict[tuple[int, bool], int] = {}
            for t in range(start, end, STEP):
                if not moving(p.pid, t):
                    continue
                me = match.hero_pos(p.pid, t)
                for e in enemies:
                    ep, ep_prev = match.hero_pos(e.pid, t), match.hero_pos(e.pid, t - 30)
                    if ep is None or ep_prev is None or not moving(e.pid, t):
                        continue
                    d = dist(ep, me)
                    if d >= radius or match.visible_to(e.hero_index, t, p.team) != 0:
                        continue
                    # the enemy's OWN velocity component towards the player (units/s)
                    to_me = ((me[0] - ep[0]) / (d or 1.0), (me[1] - ep[1]) / (d or 1.0))
                    toward = (ep[0] - ep_prev[0]) * to_me[0] + (ep[1] - ep_prev[1]) * to_me[1]
                    if toward >= approach:
                        kind = True          # hidden enemy coming at the player
                    elif toward <= 0:
                        kind = False         # control: hidden enemy as close, not coming
                    else:
                        continue
                    if t - cooldown.get((e.pid, kind), -10**9) < 300:
                        continue
                    cooldown[(e.pid, kind)] = t
                    away = turned_away(p.pid, t, ep)
                    if not kind:
                        base_n += 1
                        base_k += away
                        continue
                    episodes += 1
                    if away:
                        retreats += 1
                        f.detections.append(self.detection(
                            match, p.pid, t, f"retragere de {e.hero_short} invizibil",
                            f"{e.hero_short} venea spre jucător prin ceață (la {d:.0f} unități, nevăzut de "
                            f"echipa {'Radiant' if p.team == RADIANT else 'Dire'}) și jucătorul s-a întors "
                            f"și s-a îndepărtat în următoarele {win / 30:.1f} s.",
                            strength=0.5, enemy=e.hero_short, distance=round(d)))
            base_rate = (base_k + 1) / (base_n + 2)
            rate = retreats / episodes if episodes else 0.0
            lift = rate / base_rate if base_rate > 0 else 0.0
            pval = binom_sf(retreats, episodes, base_rate) if episodes else 1.0
            f.metrics = {"hidden_threat_episodes": episodes, "retreats": retreats,
                         "retreat_rate": round(rate, 3), "baseline_rate": round(base_rate, 3),
                         "lift": round(lift, 2), "p_value": round(pval, 4)}
            if episodes >= min_n and pval <= max_p and lift > 1:
                f.subscore = saturate(lift - 1, lift_half - 1)
            f.summary = (f"s-a retras în {retreats} din {episodes} apropieri ale unor inamici invizibili "
                         f"(de {lift:.1f}× mai des decât în mod obișnuit)" if episodes
                         else "nicio apropiere a unui inamic invizibil")
        return out
