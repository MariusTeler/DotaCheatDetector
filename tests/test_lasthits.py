import random

from synth import START, combat, make_match, order

from dotacheat.config import load_config
from dotacheat.heuristics.lasthits import LastHitHeuristic
from dotacheat.model import VisEvent

CFG = load_config()


def lh_match(delay_fn, n=40, seed=5):
    rnd = random.Random(seed)
    m = make_match(minutes=30)
    for k in range(n):
        idx = 2000 + k
        m.visibility[idx] = [VisEvent(0, 1, "npc_dota_creep_lane", 3, True, 1, 1)]
        t = START + 600 + k * 300
        d = delay_fn(rnd)
        order(m, t - d, 0, 4, target_index=idx)
        combat(m, t, "DEATH", "npc_dota_hero_axe", "npc_dota_creep_badguys_melee")
    return m


def test_human_last_hit_timing():
    f = LastHitHeuristic(CFG).run(lh_match(lambda r: r.randint(3, 35)))[0]
    assert f.metrics["timed_last_hits"] == 40 and f.subscore == 0


def test_scripted_last_hit_timing():
    f = LastHitHeuristic(CFG).run(lh_match(lambda r: 12 + r.choice([0, 0, 1])))[0]
    assert f.metrics["cv"] < 0.05 and f.subscore > 0.8 and len(f.detections) == 1


def test_too_few_samples():
    f = LastHitHeuristic(CFG).run(lh_match(lambda r: 12, n=5))[0]
    assert f.subscore == 0
