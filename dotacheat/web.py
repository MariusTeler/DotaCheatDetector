"""Tiny local web UI: paste a Match ID (or pick a local replay) and get the report.

Standard library only. Listens on 127.0.0.1 so nothing is exposed to the network.
"""

from __future__ import annotations

import html
import json
import threading
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__
from .fetch import replay_folders
from .paths import reports_dir

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
AUTO: dict = {"folders": [], "items": []}  # replays analysed automatically by the folder watcher

PAGE = """<!DOCTYPE html><html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Dota 2 – analiză replay</title>
<style>
body{font:15px/1.5 system-ui,Segoe UI,sans-serif;background:#f6f7f9;color:#1d2330;margin:0}
main{max-width:760px;margin:40px auto;padding:0 20px}
.card{background:#fff;border:1px solid #dde1e7;border-radius:10px;padding:20px;margin:14px 0}
input,select,button{font:inherit;padding:9px 12px;border-radius:8px;border:1px solid #c5cbd5}
input{width:260px}button{background:#2e86c1;color:#fff;border:0;cursor:pointer}button:disabled{opacity:.5}
.warn{border-left:5px solid #d68910;background:#fff;padding:10px 14px;border-radius:8px}
pre{background:#14171c;color:#d7dce3;padding:12px;border-radius:8px;white-space:pre-wrap;min-height:60px}
a.btn{display:inline-block;margin-top:10px;background:#2e7d32;color:#fff;padding:9px 14px;border-radius:8px;text-decoration:none}
.muted{color:#5d6675;font-size:13px}
</style></head><body><main>
<h1>Analiză replay Dota 2</h1>
<div class="warn">Rezultatul este un <b>scor de suspiciune</b> cu momente de verificat în replay, <b>nu</b> o dovadă
și nu un verdict. Aplicația citește doar fișiere de replay; nu atinge clientul Dota 2.</div>
<div class="card">
<form id="f"><label>Match ID<br><input name="match" placeholder="ex. 8552595443" inputmode="numeric"></label>
<button id="go">Analizează</button></form>
<p class="muted">Replay-ul se caută întâi în folderul local de replay-uri, apoi se descarcă prin OpenDota.</p>
__LOCAL__
</div>
<div class="card"><b>Analiză automată</b>
<p class="muted" id="autostate">__AUTOSTATE__</p><ul id="auto"></ul></div>
<div class="card"><b>Progres</b><pre id="log">—</pre><div id="res"></div></div>
<p class="muted">dotacheat __VERSION__ · rapoarte salvate în __REPORTS__</p>
</main><script>
const f=document.getElementById('f'),log=document.getElementById('log'),res=document.getElementById('res');
async function start(body){
  document.querySelectorAll('button').forEach(b=>b.disabled=true);res.innerHTML='';log.textContent='pornesc…';
  const r=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json(); if(j.error){log.textContent=j.error;document.querySelectorAll('button').forEach(b=>b.disabled=false);return}
  poll(j.job);
}
async function poll(id){
  const j=await (await fetch('/api/job/'+id)).json(); log.textContent=j.log.join('\\n');
  if(j.state==='done'){res.innerHTML=j.summary+'<br><a class="btn" href="'+j.report+'" target="_blank">Deschide raportul</a> <a href="'+j.json+'" target="_blank">JSON</a>';
    document.querySelectorAll('button').forEach(b=>b.disabled=false);return}
  if(j.state==='error'){document.querySelectorAll('button').forEach(b=>b.disabled=false);return}
  setTimeout(()=>poll(id),1000);
}
f.onsubmit=e=>{e.preventDefault();const m=f.match.value.trim();if(!/^\\d+$/.test(m)){log.textContent='Match ID invalid';return}start({match:m})};
async function auto(){
  try{const j=await (await fetch('/api/auto')).json();
    document.getElementById('auto').innerHTML=j.items.map(i=>'<li>'+i.time+' — <b>'+i.name+'</b>: '+
      (i.state==='done'?i.summary+' — <a href="'+i.report+'" target="_blank">raport</a>':(i.state==='error'?'eroare: '+i.error:'se analizează…'))+'</li>').reverse().join('');
    const n=j.items.filter(i=>i.state==='done').length; if(n) document.title='('+n+') Dota 2 – analiză replay';
  }catch(e){} setTimeout(auto,4000)}
auto();
const lf=document.getElementById('lf'); if(lf){lf.onsubmit=e=>{e.preventDefault();start({file:lf.file.value})}}
</script></body></html>"""


def _local_replays(limit: int = 40) -> list[Path]:
    files = []
    for folder in replay_folders():
        files += list(folder.glob("*.dem"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def _page() -> str:
    local = _local_replays()
    if local:
        opts = "".join(f"<option value='{html.escape(str(p))}'>{html.escape(p.name)}</option>" for p in local)
        block = (f"<form id='lf'><label>sau un replay din folderul clientului<br><select name='file'>{opts}"
                 f"</select></label> <button>Analizează fișierul</button></form>")
    else:
        block = "<p class='muted'>Nu am găsit folderul de replay-uri Dota 2 pe acest PC.</p>"
    if AUTO["folders"]:
        autostate = ("Urmăresc " + ", ".join(html.escape(str(f)) for f in AUTO["folders"]) +
                     ". Descarcă un replay din client (Watch → Replays → Download) și apare aici automat.")
    else:
        autostate = "Folderul de replay-uri nu a fost găsit, deci analiza automată e oprită."
    return (PAGE.replace("__LOCAL__", block).replace("__AUTOSTATE__", autostate).replace("__VERSION__", __version__)
            .replace("__REPORTS__", html.escape(str(reports_dir()))))


def _run_job(job_id: str, match: str | None, file: str | None) -> None:
    from .cli import run_analysis
    from .report import console_summary

    job = JOBS[job_id]

    def progress(msg: str) -> None:
        with LOCK:
            if job["log"] and msg.startswith("descărcat") and job["log"][-1].startswith("descărcat"):
                job["log"][-1] = msg
            else:
                job["log"].append(msg)

    try:
        result, html_path, json_path = run_analysis(int(match) if match else None, file, progress=progress)
        top = sorted(result.scores.values(), key=lambda s: -s.score)[:3]
        summary = "Scoruri maxime: " + ", ".join(
            f"{html.escape(result.match.players[s.pid].hero_short)} {s.score:.0f}" for s in top)
        with LOCK:
            job["log"].append("")
            job["log"].extend(console_summary(result).splitlines())
            job.update(state="done", report=f"/reports/{html_path.name}", json=f"/reports/{json_path.name}",
                       summary=summary)
    except Exception as exc:  # report every failure to the page
        with LOCK:
            job["log"].append(f"EROARE: {exc}")
            job["log"].append(traceback.format_exc(limit=3))
            job["state"] = "error"


class Handler(BaseHTTPRequestHandler):
    server_version = "dotacheat"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, _page().encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/auto":
            with LOCK:
                return self._json({"folders": [str(f) for f in AUTO["folders"]], "items": list(AUTO["items"])})
        if path.startswith("/api/job/"):
            job = JOBS.get(path.rsplit("/", 1)[-1])
            if job is None:
                return self._json({"error": "job necunoscut"}, 404)
            with LOCK:
                return self._json(dict(job))
        if path.startswith("/reports/"):
            name = Path(path).name
            target = reports_dir() / name
            if target.suffix in (".html", ".json") and target.is_file():
                ctype = "text/html" if target.suffix == ".html" else "application/json"
                return self._send(200, target.read_bytes(), ctype + "; charset=utf-8")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/analyze":
            return self._send(404, b"not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = parse_qs("")
        match = str(body.get("match") or "").strip()
        file = str(body.get("file") or "").strip()
        if match and not match.isdigit():
            return self._json({"error": "Match ID invalid"}, 400)
        if file and Path(file) not in _local_replays(10_000):
            return self._json({"error": "fișierul nu este în folderul de replay-uri"}, 400)
        if not match and not file:
            return self._json({"error": "introdu un Match ID"}, 400)
        job_id = uuid.uuid4().hex[:12]
        JOBS[job_id] = {"state": "running", "log": [], "report": None, "json": None, "summary": ""}
        threading.Thread(target=_run_job, args=(job_id, match or None, file or None), daemon=True).start()
        self._json({"job": job_id})


def _auto_analyse(path: Path) -> None:
    import time

    from .cli import run_analysis

    item = {"name": path.name, "time": time.strftime("%H:%M:%S"), "state": "running"}
    with LOCK:
        AUTO["items"].append(item)
    try:
        result, html_path, _ = run_analysis(file=str(path), progress=lambda m: None)
        top = sorted(result.scores.values(), key=lambda s: -s.score)[:3]
        summary = "scor maxim " + ", ".join(
            f"{html.escape(result.match.players[s.pid].hero_short)} {s.score:.0f}" for s in top)
        with LOCK:
            item.update(state="done", report=f"/reports/{html_path.name}", summary=summary)
    except Exception as exc:
        with LOCK:
            item.update(state="error", error=html.escape(str(exc)))


def serve(port: int = 8765, open_browser: bool = True, watch: bool = True) -> None:
    if watch:
        from .watch import ReplayWatcher

        watcher = ReplayWatcher()
        AUTO["folders"] = watcher.folders
        if watcher.folders:
            # one analysis at a time: the watcher thread runs them sequentially
            watcher.start(_auto_analyse)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Interfața rulează la {url}  (Ctrl+C pentru oprire)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
