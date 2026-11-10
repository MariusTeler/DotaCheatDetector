from __future__ import annotations

import json
from pathlib import Path

from ..scoring import to_dict

DISCLAIMER = ("Acesta este un SCOR DE SUSPICIUNE calculat din euristici statistice pe replay. "
              "NU este o dovadă și NU este un verdict 'cheater/curat'. Verificați momentele "
              "indicate în replay înainte de orice concluzie.")


def to_json_dict(result) -> dict:
    m = result.match
    return {
        "disclaimer": DISCLAIMER,
        "tool_version": result.version,
        "parser": m.parser_version,
        "generated_at": result.generated_at,
        "match": {"match_id": m.match_id, "source": m.source, "duration_s": round(m.duration_s, 1),
                  "game_start_tick": m.game_start_tick, "game_end_tick": m.game_end_tick,
                  "has_visibility": m.has_visibility, "pauses": m.pauses},
        "players": [{"pid": p.pid, "team": "radiant" if p.team == 2 else "dire", "hero": p.hero,
                     "name": p.name, "account_id": p.account_id,
                     **to_dict(result.scores[p.pid])} for p in m.players],
        "heuristics": result.heuristics,
        "findings": {key: {str(pid): f.to_dict() for pid, f in per.items()}
                     for key, per in result.findings.items()},
        "config": result.config,
    }


def write_json(result, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json_dict(result), ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8")
    return path
