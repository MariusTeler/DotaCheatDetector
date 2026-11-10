from dotacheat.heuristics.base import PlayerFinding, saturate
from dotacheat.scoring import band, combine


def test_saturate():
    assert saturate(0, 2) == 0
    assert abs(saturate(2, 2) - 0.5) < 1e-12
    assert saturate(100, 2) < 1


def test_noisy_or_combination():
    f = {"a": {0: PlayerFinding(0, 1.0, "x"), 1: PlayerFinding(1, 0.0, "")},
         "b": {0: PlayerFinding(0, 0.5, "y"), 1: PlayerFinding(1, 0.0, "")}}
    s = combine(f, {"a": 0.5, "b": 1.0})
    # 1 - (1-0.5)(1-0.5) = 0.75
    assert abs(s[0].score - 75.0) < 1e-6
    assert s[1].score == 0 and s[1].top_reasons == []
    assert abs(sum(s[0].contributions.values()) - 75.0) < 0.2
    assert len(s[0].top_reasons) == 2


def test_not_applicable_is_ignored_and_score_capped():
    na = PlayerFinding(0, 1.0, "n/a", applicable=False)
    s = combine({"a": {0: na}, "b": {0: PlayerFinding(0, 1.0, "")}}, {"a": 1, "b": 1})
    assert s[0].score == 100.0 and "a" not in s[0].contributions


def test_band_never_says_cheater():
    for x in (0, 15, 45, 99):
        label, _ = band(x)
        assert "cheat" not in label.lower()
