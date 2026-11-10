"""Run the full analysis on a folder of replays and print the score distribution.

Usage:  python tools/calibrate.py <folder-with-.dem> [--cache DIR] [--config my.toml]
Used to check false-positive rates on known-clean matches (e.g. pro games).
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotacheat.analyze import analyze  # noqa: E402
from dotacheat.config import load_config  # noqa: E402
from dotacheat.extract import load_or_parse  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--cache", type=Path, default=Path("cache/parsed"))
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    scores, per_h = [], {}
    for dem in sorted(args.folder.glob("*.dem")):
        m = load_or_parse(dem, args.cache)
        r = analyze(m, cfg)
        top = sorted(r.scores.values(), key=lambda s: -s.score)[:3]
        print(f"{m.match_id}  {m.duration_s / 60:4.0f} min  top: " + ", ".join(
            f"{m.players[s.pid].hero_short}={s.score:.0f}" for s in top))
        for s in r.scores.values():
            scores.append(s.score)
            for k, v in s.contributions.items():
                per_h.setdefault(k, []).append(v)
    if not scores:
        print("no replays found")
        return 1
    scores.sort()
    q = lambda p: scores[min(len(scores) - 1, int(p * len(scores)))]  # noqa: E731
    print(f"\n{len(scores)} players: median {statistics.median(scores):.1f}, p90 {q(0.9):.1f}, "
          f"p99 {q(0.99):.1f}, max {scores[-1]:.1f}; >=30: {sum(s >= 30 for s in scores)}, "
          f">=60: {sum(s >= 60 for s in scores)}")
    for k, v in per_h.items():
        print(f"  {k:15s} players with points: {sum(x > 0 for x in v):3d}  max {max(v):5.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
