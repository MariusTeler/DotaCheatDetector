import random

from synth import START, make_match, move, order, set_vis

from dotacheat.config import load_config
from dotacheat.heuristics.dodges import DodgeHeuristic

CFG = load_config()


def arrows(delay_fn, n=10, seed=2):
    """Mirana (pid 9, Dire, visible) shoots arrows through Axe (pid 0); Axe steps sideways."""
    rnd = random.Random(seed)
    m = make_match(minutes=40)
    for pid in (0, 9):
        set_vis(m, pid, START, radiant=True, dire=True)
    move(m, 0, START, 0.0, 0.0)
    move(m, 9, START, 1000.0, 0.0)
    for k in range(n):
        t = START + 3000 + k * 1800
        order(m, t, 9, 5, ability="mirana_arrow", x=0.0, y=0.0)
        order(m, t + delay_fn(rnd), 0, 1, x=0.0, y=500.0 * (1 if k % 2 else -1))
    return m


def test_fast_systematic_dodges_flagged():
    f = DodgeHeuristic(CFG).run(arrows(lambda r: 3))[0]
    assert f.metrics["dodged"] == 10 and f.metrics["fast_dodges"] == 10
    assert f.subscore > 0.5


def test_human_dodges_not_flagged():
    f = DodgeHeuristic(CFG).run(arrows(lambda r: r.randint(8, 20)))[0]
    assert f.metrics["dodged"] == 10 and f.subscore == 0


def test_hit_is_not_a_dodge():
    from synth import combat
    m = arrows(lambda r: 3, n=3)
    for o in [o for o in m.orders if o.ability == "mirana_arrow"]:
        combat(m, o.tick + 20, "DAMAGE", "npc_dota_hero_mirana", "npc_dota_hero_axe", "mirana_arrow", 100)
    f = DodgeHeuristic(CFG).run(m)[0]
    assert f.metrics["skillshots_through_player"] == 3 and f.metrics["dodged"] == 0
