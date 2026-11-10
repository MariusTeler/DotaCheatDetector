"""(a1) Orders on enemy heroes that the player's team could not see.

A player can only click (attack, cast on, follow) a unit that is visible to his
team. An order whose target has been in the fog for longer than network latency
can explain means the client knew the unit's whereabouts — the classic maphack
signature. Visibility comes from the replay's authoritative per-team bitsets.
"""

from __future__ import annotations

import math

from ..model import RADIANT, MatchData
from .base import Heuristic, PlayerFinding, saturate

ORDER_NAMES = {2: "urmărire (move-to-target)", 4: "atac", 6: "cast pe țintă"}
TEAM_NAMES = {2: "Radiant", 3: "Dire"}


class FogOrdersHeuristic(Heuristic):
    key = "fog_orders"
    title = "Ordine pe inamici invizibili (maphack)"
    description = ("Ordine de atac/cast/urmărire date pe eroi inamici care nu erau vizibili echipei "
                   "jucătorului în acel tick, după ce se scade toleranța pentru ping.")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        if not match.has_visibility:
            return self.not_applicable(match, "replay-ul nu conține date de vizibilitate (build vechi)")
        c = self.cfg
        order_types = set(c.get("order_types", [2, 4, 6]))
        grace = float(c.get("grace_s", 0.5))
        lat_factor = float(c.get("latency_factor", 1.0))
        min_hidden = float(c.get("min_hidden_s", 1.0))
        dedupe = float(c.get("dedupe_s", 2.0))
        hero_by_index = {p.hero_index: p for p in match.players}

        findings = {p.pid: PlayerFinding(p.pid, 0.0, "") for p in match.players}
        considered = {p.pid: 0 for p in match.players}
        last_flag: dict[tuple[int, int], int] = {}

        for o in match.orders:
            if o.order_type not in order_types or o.target_index <= 0:
                continue
            if o.tick < match.game_start_tick - 90 * 30:
                continue
            ev = match.vis_event(o.target_index, o.tick)
            if ev is None or not ev.active or not ev.name.startswith("npc_dota_hero"):
                continue
            team = match.team_of(o.pid)
            if ev.team is None or ev.team == team:
                continue
            considered[o.pid] += 1
            state = ev.radiant if team == RADIANT else ev.dire
            if state != 0:
                continue
            last_vis = match.last_visible_tick(o.target_index, o.tick, team)
            hidden_s = math.inf if last_vis is None else (o.tick - last_vis) / 30.0
            allowance = grace + lat_factor * max(o.ping_ms, o.latency_ms) / 1000.0
            if hidden_s - allowance < min_hidden:
                continue
            key = (o.pid, o.target_index)
            if key in last_flag and (o.tick - last_flag[key]) / 30.0 < dedupe:
                last_flag[key] = o.tick
                continue
            last_flag[key] = o.tick

            target_player = hero_by_index.get(o.target_index)
            target_name = (target_player.hero_short if target_player
                           else ev.name.replace("npc_dota_hero_", "") + " (iluzie/unitate)")
            me = match.hero_pos(o.pid, o.tick)
            tgt = match.hero_pos(target_player.pid, o.tick) if target_player else None
            d = math.hypot(me[0] - tgt[0], me[1] - tgt[1]) if me and tgt else None
            hidden_txt = "niciodată văzut până atunci" if math.isinf(hidden_s) else f"de {hidden_s:.1f} s"
            what = ORDER_NAMES.get(o.order_type, f"ordin {o.order_type}")
            if o.order_type == 6 and o.ability:
                what += f" ({o.ability})"
            expl = (f"Ordin de {what} pe {target_name}, care era în ceață pentru echipa "
                    f"{TEAM_NAMES.get(team, team)} {hidden_txt}. Toleranța pentru rețea era "
                    f"{allowance:.2f} s (ping {o.ping_ms} ms, latență {o.latency_ms} ms).")
            if d is not None:
                expl += f" Distanța până la țintă: {d:.0f} unități."
            strength = 1.0 if math.isinf(hidden_s) else min(1.0, (hidden_s - allowance) / 5.0 + 0.3)
            findings[o.pid].detections.append(self.detection(
                match, o.pid, o.tick, f"{what} pe {target_name} invizibil", expl, strength,
                order_type=o.order_type, target=target_name, hidden_s=None if math.isinf(hidden_s) else round(hidden_s, 2),
                allowance_s=round(allowance, 2), distance=None if d is None else round(d),
                ability=o.ability, ping_ms=o.ping_ms, latency_ms=o.latency_ms))

        hours = match.duration_s / 3600.0
        half = float(c.get("incidents_for_half", 2.0))
        min_inc = int(c.get("min_incidents", 2))
        for pid, f in findings.items():
            n = len(f.detections)
            rate = n / hours
            f.metrics = {"incidents": n, "incidents_per_hour": round(rate, 2),
                         "enemy_targeted_orders": considered[pid]}
            f.subscore = saturate(rate, half) if n >= min_inc else 0.0
            f.summary = (f"{n} ordine pe eroi inamici aflați în ceață ({rate:.1f}/oră)" if n
                         else "niciun ordin pe inamici invizibili")
        return findings
