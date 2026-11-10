from __future__ import annotations

from ..scoring import band


def console_summary(result) -> str:
    m = result.match
    lines = [
        f"Meci {m.match_id}  —  durată {int(m.duration_s // 60)}:{int(m.duration_s % 60):02d}"
        + ("" if m.has_visibility else "  (fără date de vizibilitate: euristicile de ceață sunt dezactivate)"),
        "SCOR DE SUSPICIUNE (0–100) — nu este o dovadă și nu este un verdict.",
        "",
        f"{'#':>2} {'echipa':7} {'erou':22} {'scor':>5}  {'nivel':20} motive principale",
    ]
    for p in sorted(m.players, key=lambda p: -result.scores[p.pid].score):
        s = result.scores[p.pid]
        label, _ = band(s.score)
        reason = s.top_reasons[0] if s.top_reasons else "-"
        lines.append(f"{p.pid:>2} {'Radiant' if p.team == 2 else 'Dire':7} {p.hero_short[:22]:22} "
                     f"{s.score:5.1f}  {label:20} {reason}")
    return "\n".join(lines)
