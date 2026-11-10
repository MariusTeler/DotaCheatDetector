from synth import START, make_match, move, set_vis

from dotacheat.config import load_config
from dotacheat.heuristics.fog_reactions import FogReactionsHeuristic, binom_sf

CFG = load_config()


def build(retreat_on_approach: bool, n=20):
    """Axe (pid 0) walks east. Riki (pid 5, always hidden from Radiant) either runs at him
    (approach) or walks alongside 1000 units ahead (control). Axe turns back only when
    Riki approaches (cheat) or never."""
    m = make_match(minutes=60)
    set_vis(m, 5, START, radiant=False, dire=True)
    t = START + 1800 + 60
    for k in range(2 * n):
        approaching = k % 2 == 0
        cheat_turn = approaching and retreat_on_approach
        for s in range(-150, 181, 15):  # Axe walks east (x = 10/tick); turns back at s=15 if cheating
            x = s * 10 if (s <= 15 or not cheat_turn) else 150 - (s - 15) * 15
            move(m, 0, t + s, x, 0.0)
        for s in range(-150, 181, 15):
            if approaching:   # 1500 east, then runs at Axe at 600/s
                rx = 1500 - 20 * max(0, s)
            else:             # control: 1000 units ahead of Axe, walking the same way
                rx = 1000 + 10 * s
            move(m, 5, t + s, rx, 0.0)
        t += 900
    return m


def test_no_reaction_is_clean():
    f = FogReactionsHeuristic(CFG).run(build(False))[0]
    assert f.metrics["hidden_threat_episodes"] > 5
    assert f.subscore == 0


def test_reacting_only_to_hidden_approach_is_flagged():
    f = FogReactionsHeuristic(CFG).run(build(True))[0]
    assert f.metrics["retreats"] >= 5
    assert f.metrics["lift"] > 2 and f.subscore > 0.3


def test_binom():
    assert binom_sf(0, 10, 0.1) == 1.0
    assert abs(binom_sf(10, 10, 0.5) - 0.5 ** 10) < 1e-12
