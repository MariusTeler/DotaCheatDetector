"""Locate or download replays and turn them into plain ``.dem`` files.

Sources, in order of preference for ``--match``:

1. an already-decompressed replay in the local cache;
2. ``<match_id>.dem`` in the Dota 2 client's replay folder (found through the
   Steam install / library folders on Windows) — this is only a *file read*,
   the game client is never contacted;
3. OpenDota: ``/api/matches/<id>`` gives ``replay_url`` (cluster + replay_salt).
   If OpenDota does not know the salt yet, a parse request is submitted and
   polled until the salt is available.

Valve serves replays as ``.dem.bz2`` but the payload may be bzip2 *or* Zstandard;
the format is detected from magic bytes.
"""

from __future__ import annotations

import bz2
import http.client
import json
import logging
import os
import re
import shutil
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

OPENDOTA = "https://api.opendota.com/api"
USER_AGENT = "dota-replay-analyzer/0.1"
DEM_MAGIC = b"PBDEMS2\x00"
BZ2_MAGIC = b"BZh"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

Progress = Callable[[str], None]


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Format handling
# --------------------------------------------------------------------------
def sniff(path: Path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(8)
    if head.startswith(DEM_MAGIC):
        return "dem"
    if head.startswith(BZ2_MAGIC):
        return "bz2"
    if head.startswith(ZSTD_MAGIC):
        return "zstd"
    if head.startswith(b"PBUFDEM"):
        raise FetchError(f"{path} is a Source 1 replay (pre-2015); not supported")
    raise FetchError(f"{path} is not a Dota 2 replay (unknown header {head!r})")


def _decompress(src: Path, dst: Path, kind: str) -> None:
    tmp = dst.with_suffix(dst.suffix + ".part")
    with open(src, "rb") as fin, open(tmp, "wb") as fout:
        if kind == "bz2":
            shutil.copyfileobj(bz2.BZ2File(fin), fout, 1 << 20)
        elif kind == "zstd":
            import zstandard

            zstandard.ZstdDecompressor().copy_stream(fin, fout)
        else:  # pragma: no cover
            raise FetchError(f"unexpected format {kind}")
    os.replace(tmp, dst)


def ensure_dem(path: str | Path, cache_dir: Path) -> Path:
    """Return a path to a plain .dem for *path*, decompressing (possibly nested) archives."""
    path = Path(path)
    if not path.exists():
        raise FetchError(f"file not found: {path}")
    for _ in range(3):  # bz2 containing zstd, etc.
        kind = sniff(path)
        if kind == "dem":
            return path
        cache_dir.mkdir(parents=True, exist_ok=True)
        stem = path.name.split(".")[0]
        dst = cache_dir / f"{stem}.{kind}-decoded.dem"
        if not dst.exists() or dst.stat().st_mtime < path.stat().st_mtime:
            log.info("decompressing %s (%s)", path.name, kind)
            _decompress(path, dst, kind)
        path = dst
    raise FetchError(f"{path}: too many nested archive layers")


# --------------------------------------------------------------------------
# Local Dota 2 replay folder (Windows)
# --------------------------------------------------------------------------
def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    if os.name == "nt":
        try:
            import winreg

            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for value in ("SteamPath", "InstallPath"):
                            try:
                                roots.append(Path(winreg.QueryValueEx(k, value)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:  # pragma: no cover
            pass
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            if os.environ.get(env):
                roots.append(Path(os.environ[env]) / "Steam")
    else:
        roots += [Path.home() / ".steam/steam", Path.home() / ".local/share/Steam"]
    libs: list[Path] = []
    for r in roots:
        libs.append(r)
        vdf = r / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                libs.append(Path(m.group(1).replace("\\\\", "\\")))
    seen, out = set(), []
    for lib in libs:
        key = str(lib).lower()
        if key not in seen:
            seen.add(key)
            out.append(lib)
    return out


def replay_folders() -> list[Path]:
    """All existing ``...\\dota 2 beta\\game\\dota\\replays`` folders on this machine."""
    out = []
    for lib in _steam_roots():
        p = lib / "steamapps" / "common" / "dota 2 beta" / "game" / "dota" / "replays"
        if p.is_dir():
            out.append(p)
    return out


def find_local_replay(match_id: int) -> Path | None:
    for folder in replay_folders():
        for name in (f"{match_id}.dem", f"{match_id}.dem.bz2"):
            if (folder / name).exists():
                return folder / name
    return None


# --------------------------------------------------------------------------
# OpenDota + Valve download
# --------------------------------------------------------------------------
def _api(url: str, method: str = "GET", timeout: int = 60) -> dict:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "null") or {}
    except urllib.error.HTTPError as exc:
        raise FetchError(f"OpenDota {method} {url} -> HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"cannot reach OpenDota ({exc.reason})") from exc


def replay_url(match_id: int, progress: Progress = log.info, wait_s: int = 300) -> str:
    """Return the Valve replay URL for *match_id*, asking OpenDota to fetch the salt if needed."""
    data = _api(f"{OPENDOTA}/matches/{match_id}")
    if data.get("replay_url"):
        return data["replay_url"]
    if data.get("cluster") and data.get("replay_salt"):
        return f"http://replay{data['cluster']}.valve.net/570/{match_id}_{data['replay_salt']}.dem.bz2"
    progress("OpenDota nu are încă replay_salt; trimit cerere de parsare la OpenDota…")
    job = _api(f"{OPENDOTA}/request/{match_id}", method="POST")
    job_id = (job.get("job") or {}).get("jobId") or job.get("jobId")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(10)
        if job_id is not None:
            state = _api(f"{OPENDOTA}/request/{job_id}")
            if state:  # still queued / running
                continue
        data = _api(f"{OPENDOTA}/matches/{match_id}")
        if data.get("replay_url"):
            return data["replay_url"]
        if data.get("cluster") and data.get("replay_salt"):
            return f"http://replay{data['cluster']}.valve.net/570/{match_id}_{data['replay_salt']}.dem.bz2"
    raise FetchError(
        f"OpenDota nu a putut obține replay-ul pentru meciul {match_id} în {wait_s}s. "
        "Replay-urile expiră pe serverele Valve după ~2-3 săptămâni; încearcă mai târziu "
        "sau descarcă replay-ul din client și folosește --file.")


def _open_http(url: str, timeout: int = 120):
    """GET *url*; Valve replay hosts are plain HTTP. Honours an HTTPS proxy via CONNECT."""
    u = urllib.parse.urlsplit(url)
    path = u.path + (f"?{u.query}" if u.query else "")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    no_proxy = (os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or "")
    if u.scheme == "http" and proxy and u.hostname not in no_proxy.split(","):
        p = urllib.parse.urlsplit(proxy)
        conn = http.client.HTTPConnection(p.hostname, p.port or 8080, timeout=timeout)
        conn.set_tunnel(u.hostname, u.port or 80)
    elif u.scheme == "https":
        conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=timeout,
                                           context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    conn.request("GET", path, headers={"User-Agent": USER_AGENT})
    resp = conn.getresponse()
    return conn, resp


def download(url: str, dst: Path, progress: Progress = log.info) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    conn, resp = _open_http(url)
    try:
        if resp.status == 404:
            raise FetchError("replay-ul nu mai există pe serverele Valve (404 – probabil expirat)")
        if resp.status != 200:
            raise FetchError(f"descărcare eșuată: HTTP {resp.status} pentru {url}")
        total = int(resp.getheader("Content-Length") or 0)
        done, last = 0, 0.0
        with open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if time.time() - last > 2:
                    last = time.time()
                    pct = f" ({100 * done // total}%)" if total else ""
                    progress(f"descărcat {done >> 20} MB{pct}")
    finally:
        conn.close()
    os.replace(tmp, dst)
    return dst


def obtain_replay(match_id: int, cache_dir: Path, progress: Progress = log.info) -> Path:
    """Return a plain .dem path for *match_id* (cache → local client folder → OpenDota)."""
    replays = cache_dir / "replays"
    for cand in (replays / f"{match_id}.dem",):
        if cand.exists():
            return ensure_dem(cand, replays)
    local = find_local_replay(match_id)
    if local is not None:
        progress(f"replay găsit local: {local}")
        return ensure_dem(local, replays)
    progress(f"caut replay-ul meciului {match_id} pe OpenDota…")
    url = replay_url(match_id, progress)
    progress(f"descarc {url}")
    archive = download(url, replays / f"{match_id}.dem.bz2", progress)
    dem = ensure_dem(archive, replays)
    final = replays / f"{match_id}.dem"
    if dem != final:
        os.replace(dem, final)
    archive.unlink(missing_ok=True)
    return final
