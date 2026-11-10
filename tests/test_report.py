import json

from synth import START, make_match, order, set_vis

from dotacheat.analyze import analyze
from dotacheat.config import load_config
from dotacheat.report import console_summary, write_html, write_json


def test_end_to_end_report(tmp_path):
    m = make_match()
    m.players[0].name = "<script>alert(1)</script>"
    set_vis(m, 6, START, radiant=True, dire=True)
    set_vis(m, 6, START + 100, radiant=False, dire=True)
    for k in range(4):
        order(m, START + 400 + k * 300, 0, 4, target_pid=6)
    r = analyze(m, load_config())
    assert r.scores[0].score > 30
    html = write_html(r, tmp_path / "r.html").read_text(encoding="utf-8")
    assert "<script>alert" not in html  # names are escaped
    assert "NU este o dovadă" in html and "00:13" in html
    data = json.loads(write_json(r, tmp_path / "r.json").read_text(encoding="utf-8"))
    assert data["players"][0]["score"] == r.scores[0].score
    assert data["findings"]["fog_orders"]["0"]["detections"][0]["clock"] == "00:13"
    assert "nu este un verdict" in console_summary(r)
