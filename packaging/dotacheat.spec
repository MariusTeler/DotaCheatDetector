# PyInstaller spec: build with  `pyinstaller packaging/dotacheat.spec`  (run from the repo root)
import os

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("gem", "zstandard", "snappy"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h
datas += [(os.path.join(SPECPATH, "..", "dotacheat", "default_config.toml"), "dotacheat")]
hiddenimports += ["dotacheat.heuristics." + m for m in (
    "fog_orders", "fog_reactions", "reaction_time", "scripts", "lasthits", "dodges", "cursor")]

a = Analysis(["entry.py"], pathex=[".."], datas=datas, binaries=binaries,
             hiddenimports=hiddenimports, excludes=["tkinter", "matplotlib", "IPython"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="dotacheat", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="dotacheat")
