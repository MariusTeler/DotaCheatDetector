"""(e) Orders on units that were not where the mouse cursor was.

The replay stores each player's cursor in *screen* space (``m_iCursor``,
roughly 0–510 × 0–383) but not the camera position. We recover it:

* between two move-clicks a fraction of a second apart the camera rarely
  moves, so Δworld ≈ J · Δcursor; fitting J (a small polynomial, per player)
  on those pairs gives the screen→world mapping without knowing the camera;
* the implied camera of any click is then ``click − J·cursor``.

For an attack/cast/follow order on an enemy hero we compare the hero's real
position with the point under the cursor, using the camera implied by the move
clicks just before and just after (and only when those two agree, i.e. the
camera stood still). A target far from the cursor means the order did not come
from a mouse click on that unit (script / automation), or the player acted on
a part of the map that was not on his screen.
"""

from __future__ import annotations

import bisect

import numpy as np

from ..model import ORDER_MOVE_TO_POSITION, RADIANT, MatchData
from .base import Heuristic, PlayerFinding, saturate

TARGET_ORDERS = (2, 4, 6)


def _feats(c) -> list[float]:
    x, y = c[0] / 510.0 - 0.5, c[1] / 383.0 - 0.5
    return [x, y, x * y, x * x, y * y]


def _in_hud(c) -> bool:
    """Cursor over the minimap corners or the bottom HUD (no world under the cursor)."""
    x, y = c[0] / 510.0, c[1] / 383.0
    return y > 0.78 or (y > 0.68 and (x < 0.22 or x > 0.78)) or y < 0.04


def fit_mapping(match: MatchData, pid: int):
    """Return (J, median residual, anchors) or None. anchors: (tick, camera_xy) of move clicks."""
    tr = match.cursor_tracks.get(pid)
    if tr is None or len(tr) < 50:
        return None
    mv = []
    for o in match.orders:
        if o.pid == pid and o.order_type == ORDER_MOVE_TO_POSITION:
            c = tr.at(o.tick)
            if c is not None and not _in_hud(c):
                mv.append((o.tick, c, (o.x, o.y)))
    dX, dY = [], []
    for a, b in zip(mv, mv[1:]):
        if 0 < b[0] - a[0] <= 6 and a[1] != b[1]:
            dX.append(np.subtract(_feats(b[1]), _feats(a[1])))
            dY.append(np.subtract(b[2], a[2]))
    if len(dX) < 40:
        return None
    dX, dY = np.array(dX), np.array(dY)
    keep = np.ones(len(dX), bool)
    for _ in range(3):  # robust: drop pairs where the camera did move
        J, *_ = np.linalg.lstsq(dX[keep], dY[keep], rcond=None)
        res = np.linalg.norm(dX @ J - dY, axis=1)
        keep = res <= max(60.0, np.percentile(res[keep], 75) * 1.5)
    res = np.linalg.norm(dX[keep] @ J - dY[keep], axis=1)
    anchors = [(t, (w[0] - np.dot(_feats(c), J[:, 0]), w[1] - np.dot(_feats(c), J[:, 1])))
               for t, c, w in mv]
    return J, float(np.median(res)), anchors


class CursorHeuristic(Heuristic):
    key = "cursor"
    title = "Acțiuni departe de cursor / în afara ecranului"
    description = ("Ordine pe eroi inamici aflați departe de punctul de sub cursor, cu camera nemișcată "
                   "(reconstituită din click-urile de mișcare dinainte și de după).")

    def run(self, match: MatchData) -> dict[int, PlayerFinding]:
        c = self.cfg
        max_res = float(c.get("max_fit_residual", 250))
        far = float(c.get("far_distance", 1800))
        min_far = int(c.get("min_far_orders", 10))
        half = float(c.get("far_share_for_half", 0.05))
        steady = float(c.get("camera_steady", 300))
        span = int(float(c.get("anchor_window_s", 0.5)) * 30)
        hero_by_index = {p.hero_index: p for p in match.players}
        out = {}
        for p in match.players:
            f = PlayerFinding(p.pid, 0.0, "")
            out[p.pid] = f
            fit = fit_mapping(match, p.pid)
            if fit is None or fit[1] > max_res:
                f.applicable = False
                f.summary = "cursorul nu a putut fi calibrat pentru acest jucător"
                f.metrics = {"fit_residual": None if fit is None else round(fit[1])}
                continue
            J, resid, anchors = fit
            a_ticks = [t for t, _ in anchors]
            tr = match.cursor_tracks[p.pid]
            checked = 0
            for o in match.orders:
                if o.pid != p.pid or o.order_type not in TARGET_ORDERS:
                    continue
                tgt = hero_by_index.get(o.target_index)
                if tgt is None or tgt.team == p.team:
                    continue
                cur = tr.at(o.tick)
                tpos = match.hero_pos(tgt.pid, o.tick)
                if cur is None or tpos is None or _in_hud(cur):
                    continue
                i = bisect.bisect_left(a_ticks, o.tick)
                if i == 0 or i >= len(a_ticks):
                    continue
                (tb, cb), (ta, ca) = anchors[i - 1], anchors[i]
                if o.tick - tb > span or ta - o.tick > span:
                    continue
                if np.hypot(cb[0] - ca[0], cb[1] - ca[1]) > steady:
                    continue  # camera moved in between: cannot tell
                checked += 1
                under = (cb[0] + np.dot(_feats(cur), J[:, 0]), cb[1] + np.dot(_feats(cur), J[:, 1]))
                d = float(np.hypot(under[0] - tpos[0], under[1] - tpos[1]))
                if d >= far:
                    f.detections.append(self.detection(
                        match, p.pid, o.tick, f"ordin pe {tgt.hero_short} departe de cursor",
                        f"Ordin pe {tgt.hero_short}, dar cursorul arăta spre un punct aflat la ~{d:.0f} unități "
                        f"de erou (camera stătea pe loc: click-uri la {match.clock(tb)} și {match.clock(ta)}). "
                        f"Ținta probabil nu era sub cursor, poate nici pe ecran.",
                        strength=min(1.0, d / (2 * far)), target=tgt.hero_short, distance=round(d),
                        visible_to_team=match.visible_to(tgt.hero_index, o.tick, p.team)))
            k = len(f.detections)
            share = k / checked if checked else 0.0
            f.metrics = {"fit_residual": round(resid), "checked_orders": checked, "far_orders": k,
                         "far_share": round(share, 3)}
            if k >= min_far:
                f.subscore = saturate(share, half)
            f.summary = (f"{k} din {checked} ordine pe inamici departe de cursor" if checked
                         else "niciun ordin verificabil")
        return out
