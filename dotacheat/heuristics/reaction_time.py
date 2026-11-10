"""(b) Inhumanly fast defensive reactions.

Trigger (server tick at which the threat became perceivable):
  * an enemy hero, visible to the player's team, issues a cast of a known threat
    (Hook, Arrow, Hex, Duel, Blink…) that targets the player, lands near him, or
    starts near him;
  * an enemy hero *appears* out of the fog close to the player.
Response: the player's next defensive/escape cast (Blink, BKB, Manta, Eul,
Force, Glimmer, TP, Shadow Dance, …) within ``max_window_ms``.

Reaction = (response tick - trigger tick) - ping_correction * ping. A real
reaction cannot reach the server sooner than one round trip after the event,
so responses arriving earlier than ``ping - physical_slack_ms`` are not
reactions at all (simultaneous actions, or the player's own move revealing the
enemy) and are excluded. Client-side interpolation is *not* subtracted, which
over-estimates reaction times (fewer false positives). Human visual reaction is
~200–300 ms even for top players; we score the per-match distribution, not
isolated events.
"""

from __future__ import annotations

import bisect
import math
import statistics

from ..gamedata import RESPONSES, THREATS
from ..model import CAST_ORDERS, RADIANT, MatchData, ORDER_CAST_NO_TARGET, ORDER_CAST_POSITION, ORDER_CAST_TARGET, dist
from .base import Heuristic, PlayerFinding, saturate

MS_PER_TICK = 1000.0 / 30.0


def _seg_dist(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def threat_triggers(match: MatchData, pid: int, radius: float) -> list[tuple[int, str]]:
    """(tick, description) of threats aimed at player *pid*."""
    me = match.players[pid]
    out: list[tuple[int, str]] = []
    enemies = {p.pid for p in match.players if p.team != me.team}
    for o in match.orders:
        if o.pid not in enemies or o.order_type not in CAST_ORDERS or o.ability not in THREATS:
            continue
        enemy = match.players[o.pid]
        if match.visible_to(enemy.hero_index, o.tick, me.team) != 1:
            continue  # the player could not see the enemy start the cast
        my_pos = match.hero_pos(pid, o.tick)
        en_pos = match.hero_pos(o.pid, o.tick)
        if my_pos is None or en_pos is None:
            continue
        hit = False
        if o.order_type == ORDER_CAST_TARGET:
            hit = o.target_index == me.hero_index
        elif o.order_type == ORDER_CAST_POSITION:
            if dist(en_pos, my_pos) <= radius:
                # landing near me, or a line skillshot passing near me
                ex = (o.x - en_pos[0], o.y - en_pos[1])
                L = math.hypot(*ex) or 1.0
                far = (en_pos[0] + ex[0] / L * radius, en_pos[1] + ex[1] / L * radius)
                hit = dist((o.x, o.y), my_pos) <= 450 or _seg_dist(my_pos, en_pos, far) <= 250
        elif o.order_type == ORDER_CAST_NO_TARGET:
            hit = dist(en_pos, my_pos) <= 700
        if hit:
            out.append((o.tick, f"{enemy.hero_short} a început {o.ability}"))
    # enemies popping out of the fog nearby
    for e in enemies:
        idx = match.players[e].hero_index
        prev = None
        for ev in match.visibility.get(idx, []):
            state = ev.radiant if me.team == RADIANT else ev.dire
            if prev == 0 and state == 1 and ev.active:
                d = dist(match.hero_pos(e, ev.tick), match.hero_pos(pid, ev.tick))
                # skip if the player himself jumped (blink/leap) into vision just now
                p_now = match.hero_pos(pid, ev.tick)
                p_before = match.hero_pos(pid, ev.tick - 10)
                jumped = dist(p_now, p_before) > 450
                if d <= radius * 0.75 and not jumped:
                    out.append((ev.tick, f"{match.players[e].hero_short} a apărut din ceață la {d:.0f} unități"))
            prev = state
    out.sort()
    return out


class ReactionTimeHeuristic(Heuristic):
    key = "reaction_time"
    title = "Timp de reacție inuman"
    description = ("Distribuția timpilor dintre o amenințare vizibilă (cast inamic pe/înspre jucător, "
                   "inamic apărut din ceață) și răspunsul defensiv al jucătorului (Blink, BKB, Manta, "
                   "Eul, Force, TP…), corectat cu ping-ul. Sub ~120 ms în mod repetat e neobișnuit.")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        c = self.cfg
        fast = float(c.get("fast_ms", 120))
        window = float(c.get("max_window_ms", 1000))
        corr = float(c.get("ping_correction", 1.0))
        slack = float(c.get("physical_slack_ms", 30))
        radius = float(c.get("trigger_radius", 1400))
        min_fast = int(c.get("min_fast", 3))
        min_samples = int(c.get("min_samples", 4))
        half = float(c.get("fast_share_for_half", 0.25))
        max_p = float(c.get("max_p_value", 0.002))
        spam_ticks = int(float(c.get("spam_window_s", 0.5)) * 30)
        out = {}
        for p in match.players:
            f = PlayerFinding(p.pid, 0.0, "")
            out[p.pid] = f
            if not match.has_visibility:
                f.applicable = False
                f.summary = "fără date de vizibilitate"
                continue
            trig = threat_triggers(match, p.pid, radius)
            trig_ticks = [t for t, _ in trig]

            def classify(tick: int, ping: int):
                """Latest trigger this tick could be a reaction to -> (index, raw_ms, rt) or None."""
                i = bisect.bisect_right(trig_ticks, tick) - 1
                while i >= 0:
                    raw_ms = (tick - trig_ticks[i]) * MS_PER_TICK
                    if raw_ms > window:
                        return None
                    if tick == trig_ticks[i]:
                        i -= 1
                        continue  # same server tick: cannot be a reaction to it
                    rt = raw_ms - corr * ping
                    if rt >= -slack:
                        return i, raw_ms, max(0.0, rt)
                    i -= 1
                return None

            offsets = [d for d in range(-90, 91, 3) if abs(d) >= 15]
            used_ok = successful_casts(match, p.pid)
            last_press: dict[str, int] = {}
            rts: list[float] = []
            expected = 0.0
            in_context = 0
            for o in match.orders:
                if o.pid != p.pid or o.order_type not in CAST_ORDERS or o.ability not in RESPONSES:
                    continue
                if p.hero_index not in o.units:
                    continue
                prev = last_press.get(o.ability)
                last_press[o.ability] = o.tick
                if prev is not None and o.tick - prev < spam_ticks:
                    continue  # key spam: not a measurable reaction
                if not _succeeded(used_ok.get(o.ability, []), o.tick):
                    continue  # order rejected (cooldown, stunned, out of range...)
                lo = bisect.bisect_left(trig_ticks, o.tick - 120)
                if lo >= len(trig_ticks) or trig_ticks[lo] > o.tick + 120:
                    continue  # no threat around: not a candidate reaction at all
                in_context += 1
                # surrogate: how often would this cast look "fast" if it happened a bit earlier/later?
                hits = 0
                for d in offsets:
                    r = classify(o.tick + d, o.ping_ms)
                    hits += bool(r and r[2] < fast)
                expected += hits / len(offsets)
                r = classify(o.tick, o.ping_ms)
                if r is None:
                    continue
                i, raw_ms, rt = r
                rts.append(rt)
                if rt < fast:
                    f.detections.append(self.detection(
                        match, p.pid, o.tick, f"{o.ability} după {rt:.0f} ms",
                        f"{trig[i][1]} la {match.clock(trig_ticks[i])}; jucătorul a răspuns cu {o.ability} "
                        f"după {raw_ms:.0f} ms pe server, adică ~{rt:.0f} ms după scăderea ping-ului "
                        f"({o.ping_ms} ms). Reacția vizuală umană tipică e 200–300 ms.",
                        strength=1.0 - rt / fast, response=o.ability, trigger=trig[i][1],
                        raw_ms=round(raw_ms), corrected_ms=round(rt), ping_ms=o.ping_ms))
            n, k = len(rts), len(f.detections)
            excess = k - expected
            pval = poisson_sf(k, expected)
            f.metrics = {"measured_reactions": n, "fast_reactions": k,
                         "expected_fast_by_chance": round(expected, 1), "p_value": round(pval, 4),
                         "median_ms": round(statistics.median(rts)) if rts else None,
                         "reaction_ms": [round(x) for x in rts]}
            if n >= min_samples and excess >= min_fast and pval <= max_p:
                f.subscore = saturate(excess / max(1, in_context), half)
            if n:
                f.summary = (f"{k} din {n} reacții defensive sub {fast:.0f} ms "
                             f"(așteptat din întâmplare ≈{expected:.1f}; mediana {f.metrics['median_ms']} ms)")
            else:
                f.summary = "nicio reacție defensivă măsurabilă"
        return out


def successful_casts(match: MatchData, pid: int) -> dict[str, list[int]]:
    """Combat-log ticks at which the player's hero actually used each ability/item."""
    hero = match.players[pid].hero
    out: dict[str, list[int]] = {}
    for e in match.combat:
        if e.type in ("ABILITY", "ITEM") and e.attacker == hero and not e.attacker_illusion and e.inflictor:
            out.setdefault(e.inflictor, []).append(e.tick)
    return out


def _succeeded(ticks: list[int], order_tick: int, within: int = 45) -> bool:
    i = bisect.bisect_left(ticks, order_tick)
    return i < len(ticks) and ticks[i] - order_tick <= within


def poisson_sf(k: int, lam: float) -> float:
    """P(X >= k) for X ~ Poisson(lam)."""
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    term = math.exp(-lam)
    cdf = term
    for i in range(1, k):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)
