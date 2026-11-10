"""Self-contained local HTML report (no external resources)."""

from __future__ import annotations

from html import escape
from pathlib import Path

from ..scoring import band
from .json_export import DISCLAIMER

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--muted:#5d6675;--line:#dde1e7;
--high:#c0392b;--mid:#d68910;--low:#2e86c1;--none:#7f8c8d;--rad:#2e7d32;--dire:#b71c1c}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--ink:#e6e9ee;--muted:#9aa3b2;--line:#2c323c}}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
main{max-width:1100px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}h3{font-size:15px;margin:16px 0 6px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.warn{border-left:5px solid var(--mid);background:var(--card);padding:12px 16px;border-radius:8px;margin:14px 0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.score{font-weight:700;font-variant-numeric:tabular-nums;font-size:16px}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;color:#fff}
.high{background:var(--high)}.mid{background:var(--mid)}.low{background:var(--low)}.none{background:var(--none)}
.team-2{color:var(--rad);font-weight:600}.team-3{color:var(--dire);font-weight:600}
.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;min-width:80px}.bar>i{display:block;height:100%}
.t{font-family:ui-monospace,Consolas,monospace;font-weight:600;white-space:nowrap}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}
.na{opacity:.6}.metrics{font-size:12px;color:var(--muted)}
ul.reasons{margin:0;padding-left:18px}
.hist{display:flex;align-items:flex-end;gap:2px;height:70px;margin:6px 0}.hist>div{flex:1;background:var(--low);min-height:1px}
.hist>div.fast{background:var(--high)}
"""


def _hist(values: list[float], fast: float, width_ms: int = 50, max_ms: int = 1000) -> str:
    if not values:
        return ""
    bins = [0] * (max_ms // width_ms)
    for v in values:
        i = int(max(0, min(max_ms - 1, v)) // width_ms)
        bins[i] += 1
    peak = max(bins) or 1
    cols = "".join(
        f'<div class="{"fast" if (i + 1) * width_ms <= fast else ""}" style="height:{100 * b / peak:.0f}%" '
        f'title="{i * width_ms}–{(i + 1) * width_ms} ms: {b}"></div>' for i, b in enumerate(bins))
    return (f'<div class="hist">{cols}</div><div class="metrics">0 ms … {max_ms} ms '
            f'(roșu = sub {fast:.0f} ms)</div>')


def render_html(result) -> str:
    m = result.match
    titles = {h["key"]: h["title"] for h in result.heuristics}
    rows = []
    for p in sorted(m.players, key=lambda p: -result.scores[p.pid].score):
        s = result.scores[p.pid]
        label, cls = band(s.score)
        reasons = "".join(f"<li>{escape(r)}</li>" for r in s.top_reasons) or "<li class='muted'>—</li>"
        rows.append(
            f"<tr><td>{p.pid}</td><td class='team-{p.team}'>{'Radiant' if p.team == 2 else 'Dire'}</td>"
            f"<td><a href='#p{p.pid}'>{escape(p.hero_short)}</a><div class='muted'>{escape(p.name)}</div></td>"
            f"<td class='score'>{s.score:.0f}</td>"
            f"<td><span class='pill {cls}'>{label}</span>"
            f"<div class='bar'><i class='{cls}' style='width:{s.score:.0f}%'></i></div></td>"
            f"<td><ul class='reasons'>{reasons}</ul></td></tr>")

    sections = []
    for p in m.players:
        s = result.scores[p.pid]
        label, cls = band(s.score)
        blocks = []
        for key, per in result.findings.items():
            f = per[p.pid]
            pts = s.contributions.get(key, 0.0)
            metrics = ", ".join(f"{escape(str(k))}={escape(str(v))}" for k, v in f.metrics.items()
                                if not isinstance(v, (list, dict)))
            hist = ""
            if isinstance(f.metrics.get("reaction_ms"), list):
                hist = _hist(f.metrics["reaction_ms"], float(result.config.get(key, {}).get("fast_ms", 120)))
            det_rows = "".join(
                f"<tr><td class='t'>{escape(d.clock)}</td><td>{escape(d.title)}</td>"
                f"<td>{escape(d.explanation)}</td></tr>" for d in f.detections[:200])
            more = (f"<div class='muted'>… încă {len(f.detections) - 200} momente în exportul JSON</div>"
                    if len(f.detections) > 200 else "")
            det = (f"<table><tr><th>timp meci</th><th>ce</th><th>de ce e suspect</th></tr>{det_rows}</table>{more}"
                   if det_rows else "")
            open_attr = " open" if f.detections and f.subscore > 0 else ""
            blocks.append(
                f"<details class='{'' if f.applicable else 'na'}'{open_attr}><summary>{escape(titles.get(key, key))}"
                f" — <span class='muted'>{escape(f.summary)}</span>"
                f" <span class='muted'>(sub-scor {f.subscore:.2f}, +{pts:.0f} puncte)</span></summary>"
                f"<div class='metrics'>{metrics}</div>{hist}{det}</details>")
        sections.append(
            f"<div class='card' id='p{p.pid}'><h3><span class='team-{p.team}'>{'Radiant' if p.team == 2 else 'Dire'}</span>"
            f" · {escape(p.hero_short)} · {escape(p.name)} — scor <span class='score'>{s.score:.0f}</span> "
            f"<span class='pill {cls}'>{label}</span></h3>{''.join(blocks)}</div>")

    heur = "".join(f"<li><b>{escape(h['title'])}</b>: {escape(h['description'])}</li>" for h in result.heuristics)
    vis_note = ("" if m.has_visibility else
                "<div class='warn'>Replay-ul nu conține date de vizibilitate per echipă (build vechi). "
                "Euristicile bazate pe ceață (maphack) nu au putut fi aplicate.</div>")
    return f"""<!DOCTYPE html><html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analiză replay {m.match_id}</title><style>{CSS}</style></head><body><main>
<h1>Analiză replay — meciul {m.match_id}</h1>
<div class="muted">Durată {int(m.duration_s // 60)}:{int(m.duration_s % 60):02d} · generat {escape(result.generated_at)} ·
{escape(m.parser_version)} · sursă {escape(Path(m.source).name)}</div>
<div class="warn"><b>Important:</b> {escape(DISCLAIMER)} Timpii (MM:SS) sunt ceasul din joc; în clientul Dota 2
deschideți replay-ul și derulați la acel moment, din perspectiva jucătorului respectiv.</div>
{vis_note}
<h2>Jucători</h2><div class="card"><table>
<tr><th>#</th><th>echipa</th><th>erou / jucător</th><th>scor</th><th>nivel</th><th>motive principale</th></tr>
{''.join(rows)}</table></div>
<h2>Detalii pe jucător</h2>{''.join(sections)}
<h2>Metodă</h2><div class="card"><ul>{heur}</ul>
<p class="muted">Scorul combină sub-scorurile euristicilor (0–1) prin „noisy-OR” ponderat:
100·(1 − Π(1 − wₕ·sₕ)). Fiecare euristică normalizează la frecvența evenimentelor (pe oră sau ca proporție
din oportunități), deci un meci lung nu pare automat mai suspect. Pragurile și ponderile sunt în
fișierul de configurare.</p></div>
</main></body></html>"""


def write_html(result, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(result), encoding="utf-8")
    return path
