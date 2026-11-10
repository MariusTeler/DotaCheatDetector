import random

from synth import START, combat, make_match, order

from dotacheat.config import load_config
from dotacheat.heuristics.scripts import ScriptHeuristic

CFG = load_config()
COMBO = ["item_blink", "enigma_black_hole", "item_refresher", "item_shivas_guard"]


def combo_match(gaps_fn, repeats=5, seed=3):
    rnd = random.Random(seed)
    m = make_match(minutes=40)
    for r in range(repeats):
        t = START + 6000 * (r + 1)
        for i, a in enumerate(COMBO):
            order(m, t, 3, 8, ability=a)
            combat(m, t + 30, "ITEM", m.players[3].hero, "", a)  # completion well after the next order
            if i < 3:
                t += gaps_fn(rnd, i)
    return m


def test_identical_repeated_combo_is_flagged():
    m = combo_match(lambda r, i: [4, 7, 9][i])
    f = ScriptHeuristic(CFG).run(m)[3]
    seq = [d for d in f.detections if d.data["kind"] == "repeated_sequence"]
    assert len(seq) == 1 and seq[0].data["repeats"] == 5
    assert seq[0].data["sequence"] == COMBO  # longest sequence reported, not its sub-sequences


def test_human_jitter_is_not_flagged():
    m = combo_match(lambda r, i: [4, 7, 9][i] + r.randint(-2, 2))
    f = ScriptHeuristic(CFG).run(m)[3]
    assert [d for d in f.detections if d.data["kind"] == "repeated_sequence"] == []


def test_engine_buffered_orders_are_not_flagged():
    # every next order coincides with the previous cast completing => game timing, not player
    m = make_match(minutes=40)
    for r in range(5):
        t = START + 6000 * (r + 1)
        for a in COMBO:
            order(m, t, 3, 8, ability=a)
            t += 12
            combat(m, t, "ABILITY", m.players[3].hero, "", a)  # completes when the next order lands
    f = ScriptHeuristic(CFG).run(m)[3]
    assert [d for d in f.detections if d.data["kind"] == "repeated_sequence"] == []


def test_same_tick_multicast():
    m = make_match()
    for k in range(3):
        t = START + 5000 + k * 4000
        for a in COMBO[:3]:
            order(m, t, 3, 8, ability=a)
            combat(m, t + 20, "ITEM", m.players[3].hero, "", a)
    f = ScriptHeuristic(CFG).run(m)[3]
    assert f.metrics["same_tick_multicasts"] == 3
    assert f.subscore > 0
