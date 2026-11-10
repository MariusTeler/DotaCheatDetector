"""Watch the Dota 2 replay folder(s) and analyse every new replay automatically.

Only the file system is polled: the game client is never contacted. When the
client downloads a replay it writes ``<match_id>.dem`` into its ``replays``
folder; we wait until the file stops growing (download/extraction finished),
check the header, then run the normal analysis.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from .fetch import DEM_MAGIC, replay_folders

Callback = Callable[[Path], None]


class ReplayWatcher:
    def __init__(self, folders: list[Path] | None = None, interval_s: float = 3.0,
                 stable_s: float = 6.0, include_existing: bool = False):
        self.folders = [Path(f) for f in (folders or replay_folders())]
        self.interval = interval_s
        self.stable = stable_s
        self._seen: set[Path] = set() if include_existing else set(self._list())
        self._pending: dict[Path, tuple[int, float]] = {}  # path -> (size, since)
        self._stop = threading.Event()

    def _list(self) -> list[Path]:
        out = []
        for folder in self.folders:
            if folder.is_dir():
                out += [p for p in folder.glob("*.dem") if p.is_file()]
        return out

    @staticmethod
    def _complete(path: Path) -> bool:
        try:
            with open(path, "rb") as fh:  # fails while the client still holds it exclusively
                return fh.read(8) == DEM_MAGIC
        except OSError:
            return False

    def poll(self, now: float | None = None) -> list[Path]:
        """One scan. Returns replays that just became ready (each reported once)."""
        now = time.time() if now is None else now
        ready = []
        for p in self._list():
            if p in self._seen:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            prev = self._pending.get(p)
            if prev is None or prev[0] != size:
                self._pending[p] = (size, now)  # new or still growing
                continue
            if size > 1_000_000 and now - prev[1] >= self.stable and self._complete(p):
                self._pending.pop(p, None)
                self._seen.add(p)
                ready.append(p)
        return ready

    def run(self, on_ready: Callback) -> None:
        while not self._stop.is_set():
            for p in self.poll():
                on_ready(p)
            self._stop.wait(self.interval)

    def start(self, on_ready: Callback) -> threading.Thread:
        t = threading.Thread(target=self.run, args=(on_ready,), daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()


def watch_cli(open_report: bool = True, include_existing: bool = False, config: str | None = None,
              folders: list[Path] | None = None) -> int:
    """``dotacheat watch``: analyse each new replay, print the summary, open the report."""
    import webbrowser

    from .cli import run_analysis
    from .report import console_summary

    w = ReplayWatcher(folders=folders, include_existing=include_existing)
    if not w.folders:
        print("Nu am găsit folderul de replay-uri Dota 2. Folosește: dotacheat watch --folder <cale>")
        return 2
    print("Urmăresc folderele:")
    for f in w.folders:
        print("  ", f)
    print("Descarcă un replay din client (Watch → Replays → Download); îl analizez automat. Ctrl+C pentru oprire.\n")

    def handle(path: Path) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] replay nou: {path.name}")
        try:
            result, html, _js = run_analysis(file=str(path), config=config)
        except Exception as exc:  # keep watching
            print(f"  eroare la analiză: {exc}")
            return
        print(console_summary(result))
        print(f"  raport: {html}\n")
        if open_report:
            webbrowser.open(html.resolve().as_uri())

    try:
        w.run(handle)
    except KeyboardInterrupt:
        pass
    return 0
