"""(d1) Last hits / denies with near-constant timing.

For every creep a hero last-hits (or denies) we take the time between the
player's last attack order on a creep and the creep's death. Humans either
right-click early and let the auto-attack land, or click "about now" with tens
of ms of jitter, so the delay varies a lot (coefficient of variation 0.3–1.3 in
the pro games we calibrated on). A last-hit script issues the attack exactly
when HP drops under the hero's damage, giving a near-constant delay.
"""

from __future__ import annotations

import bisect
import statistics

from ..model import ORDER_ATTACK_TARGET, MatchData
from .base import Heuristic, PlayerFinding


class LastHitHeuristic(Heuristic):
    key = "lasthits"
    title = "Last hit / deny cu timing constant"
    description = ("Variația timpului dintre ultimul ordin de atac pe un creep și moartea creep-ului. "
                   "O variație anormal de mică pe zeci de last hit-uri sugerează un script de last hit.")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        c = self.cfg
        window = int(float(c.get("window_s", 1.5)) * 30)
        min_n = int(c.get("min_samples", 25))
        cv_half = float(c.get("cv_for_half", 0.15))
        cv_human = float(c.get("cv_human", 0.30))
        out = {}
        for p in match.players:
            f = PlayerFinding(p.pid, 0.0, "")
            out[p.pid] = f
            deaths = [e.tick for e in match.combat if e.type == "DEATH" and e.attacker == p.hero
                      and not e.attacker_illusion and e.target.startswith("npc_dota_creep")]
            attacks = []
            for o in match.orders:
                if o.pid != p.pid or o.order_type != ORDER_ATTACK_TARGET:
                    continue
                ev = match.vis_event(o.target_index, o.tick)
                if ev is not None and ev.name.startswith("npc_dota_creep"):
                    attacks.append(o.tick)
            delays = []
            for t in deaths:
                i = bisect.bisect_right(attacks, t) - 1
                if i >= 0 and t - attacks[i] <= window:
                    delays.append(t - attacks[i])
            n = len(delays)
            f.metrics = {"creep_kills": len(deaths), "timed_last_hits": n}
            if n < min_n:
                f.summary = f"prea puține last hit-uri măsurabile ({n})"
                continue
            mean = statistics.fmean(delays)
            sd = statistics.pstdev(delays)
            cv = sd / mean if mean > 0 else 0.0
            f.metrics.update({"mean_delay_ms": round(mean * 1000 / 30), "std_delay_ms": round(sd * 1000 / 30),
                              "cv": round(cv, 3)})
            if cv < cv_human:
                f.subscore = min(1.0, 0.5 * (cv_human - cv) / max(1e-9, cv_human - cv_half))
                f.detections.append(self.detection(
                    match, p.pid, match.game_start_tick,
                    f"timing de last hit foarte constant (CV {cv:.2f})",
                    f"Pe {n} last hit-uri, timpul dintre ultimul ordin de atac și moartea creep-ului a fost "
                    f"{mean * 1000 / 30:.0f} ± {sd * 1000 / 30:.0f} ms (CV {cv:.2f}). La jucătorii umani, "
                    f"inclusiv profesioniști, CV-ul este de obicei peste {cv_human:.2f}.",
                    strength=f.subscore, cv=round(cv, 3), samples=n))
            f.summary = f"CV timing last hit {cv:.2f} pe {n} last hit-uri"
        return out
