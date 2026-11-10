"""Command line: ``dotacheat analyze --match 1234567890`` or ``dotacheat analyze --file x.dem``."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__
from .analyze import analyze
from .config import load_config
from .extract import load_or_parse
from .fetch import FetchError, ensure_dem, obtain_replay, replay_folders
from .paths import cache_dir, reports_dir
from .report import console_summary, write_html, write_json


def run_analysis(match_id: int | None = None, file: str | None = None, config: str | None = None,
                 out_dir: Path | None = None, cache: Path | None = None, progress=print):
    cache = Path(cache) if cache else cache_dir()
    out_dir = Path(out_dir) if out_dir else reports_dir()
    cfg = load_config(config)
    if file:
        dem = ensure_dem(file, cache / "replays")
    else:
        dem = obtain_replay(int(match_id), cache, progress)
    progress(f"parsez {dem.name} (durează ~1 minut)…")
    t0 = time.time()
    match = load_or_parse(dem, cache / "parsed")
    progress(f"parsare gata în {time.time() - t0:.0f} s; rulez euristicile…")
    result = analyze(match, cfg)
    stem = f"match_{match.match_id or Path(dem).stem}"
    html = write_html(result, out_dir / f"{stem}.html")
    js = write_json(result, out_dir / f"{stem}.json")
    return result, html, js


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dotacheat", description=(
        "Analizează replay-uri Dota 2 (.dem) după meci și calculează un SCOR DE SUSPICIUNE "
        "(nu un verdict). Nu interacționează cu clientul jocului."))
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analizează un meci")
    src = a.add_mutually_exclusive_group(required=True)
    src.add_argument("--match", type=int, help="Match ID (replay descărcat prin OpenDota)")
    src.add_argument("--file", help="fișier .dem / .dem.bz2 local")
    a.add_argument("--config", help="fișier TOML cu praguri/ponderi (suprascrie valorile implicite)")
    a.add_argument("--out", type=Path, help=f"folder pentru rapoarte (implicit {reports_dir()})")
    a.add_argument("--cache", type=Path, help=f"folder cache (implicit {cache_dir()})")
    a.add_argument("--open", action="store_true", help="deschide raportul HTML în browser")
    a.add_argument("-v", "--verbose", action="store_true")
    sub.add_parser("folders", help="afișează folderele de replay-uri Dota 2 găsite pe acest PC")
    g = sub.add_parser("gui", help="pornește interfața web locală")
    g.add_argument("--port", type=int, default=8765)
    g.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "folders":
        folders = replay_folders()
        print("\n".join(map(str, folders)) if folders else "niciun folder de replay-uri găsit")
        return 0
    if args.cmd == "gui":
        from .web import serve

        serve(port=args.port, open_browser=not args.no_browser)
        return 0

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        result, html, js = run_analysis(args.match, args.file, args.config, args.out, args.cache)
    except FetchError as exc:
        print(f"eroare: {exc}", file=sys.stderr)
        return 2
    print()
    print(console_summary(result))
    print()
    print(f"raport HTML: {html}")
    print(f"export JSON: {js}")
    if args.open:
        import webbrowser

        webbrowser.open(html.resolve().as_uri())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
