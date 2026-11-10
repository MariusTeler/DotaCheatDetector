import bz2

import pytest
import zstandard

from dotacheat.fetch import DEM_MAGIC, FetchError, ensure_dem, sniff


def test_detects_and_unpacks_nested_archives(tmp_path):
    raw = DEM_MAGIC + b"payload" * 100
    zst = zstandard.ZstdCompressor().compress(raw)
    nested = tmp_path / "1.dem.bz2"
    nested.write_bytes(bz2.compress(zst))  # bz2 containing zstd
    assert sniff(nested) == "bz2"
    out = ensure_dem(nested, tmp_path / "cache")
    assert out.read_bytes() == raw


def test_plain_dem_is_returned_as_is(tmp_path):
    p = tmp_path / "x.dem"
    p.write_bytes(DEM_MAGIC + b"x")
    assert ensure_dem(p, tmp_path / "c") == p


def test_rejects_non_replay(tmp_path):
    p = tmp_path / "x.dem"
    p.write_bytes(b"hello world")
    with pytest.raises(FetchError):
        ensure_dem(p, tmp_path / "c")
