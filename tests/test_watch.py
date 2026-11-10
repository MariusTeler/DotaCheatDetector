from dotacheat.fetch import DEM_MAGIC
from dotacheat.watch import ReplayWatcher


def test_existing_files_are_skipped_new_ones_reported_once_when_stable(tmp_path):
    (tmp_path / "1.dem").write_bytes(DEM_MAGIC + b"x" * 2_000_000)
    w = ReplayWatcher([tmp_path], stable_s=5)
    new = tmp_path / "2.dem"
    new.write_bytes(DEM_MAGIC + b"x" * 1_500_000)
    assert w.poll(now=0) == []          # first sighting
    with open(new, "ab") as fh:         # still downloading: grows
        fh.write(b"x" * 600_000)
    assert w.poll(now=3) == []
    assert w.poll(now=6) == []          # stable for only 3 s
    assert w.poll(now=9) == [new]       # stable for 6 s -> ready
    assert w.poll(now=20) == []         # reported once


def test_incomplete_or_tiny_files_are_not_reported(tmp_path):
    w = ReplayWatcher([tmp_path], stable_s=1)
    (tmp_path / "3.dem").write_bytes(b"\0" * 2_000_000)   # header not written yet
    (tmp_path / "4.dem").write_bytes(DEM_MAGIC + b"x")     # too small
    for t in (0, 5, 10):
        assert w.poll(now=t) == []


def test_include_existing(tmp_path):
    p = tmp_path / "5.dem"
    p.write_bytes(DEM_MAGIC + b"x" * 2_000_000)
    w = ReplayWatcher([tmp_path], stable_s=1, include_existing=True)
    w.poll(now=0)
    assert w.poll(now=2) == [p]
