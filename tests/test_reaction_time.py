import random

from synth import START, combat, make_match, move, order, set_vis

from dotacheat.config import load_config
from dotacheat.heuristics.reaction_time import ReactionTimeHeuristic, poisson_sf

CFG = load_config()


def scenario(delay_ticks, n=8, ping=40, seed=1):
    """Lion (pid 6, Dire) hexes Axe (pid 0) n times; Axe answers with BKB after delay_ticks."""
    rnd = random.Random(seed)
    m = make_match(minutes=40)
    for pid in (0, 6):
        set_vis(m, pid, START, radiant=True, dire=True)
    move(m, 0, START, 0.0, 0.0)
    move(m, 6, START, 500.0, 0.0)
    for k in range(n):
        t = START + 3000 + k * 3000
        order(m, t, 6, 6, target_pid=0, ability="lion_voodoo")
        d = delay_ticks(rnd) if callable(delay_ticks) else delay_ticks
        order(m, t + d, 0, 8, ability="item_black_king_bar", ping=ping)
        combat(m, t + d, "ITEM", "npc_dota_hero_axe", "", "item_black_king_bar")
    return m


def test_human_reactions_are_not_flagged():
    m = scenario(lambda r: r.randint(9, 16))  # 300-530 ms server time
    f = ReactionTimeHeuristic(CFG).run(m)[0]
    assert f.metrics["measured_reactions"] == 8
    assert f.subscore == 0 and f.detections == []
    assert 200 < f.metrics["median_ms"] < 500


def test_inhuman_repeated_reactions_are_flagged():
    m = scenario(3)  # 100 ms on the server with 40 ms ping -> ~60 ms reaction
    f = ReactionTimeHeuristic(CFG).run(m)[0]
    assert len(f.detections) == 8
    assert f.subscore > 0.5
    assert f.metrics["p_value"] < 0.002
    assert "lion_voodoo" in f.detections[0].explanation


def test_physically_impossible_timing_is_not_a_reaction():
    m = scenario(0)  # same tick as the trigger: simultaneous, not a reaction
    f = ReactionTimeHeuristic(CFG).run(m)[0]
    assert f.detections == [] and f.metrics["measured_reactions"] == 0


def test_key_spam_and_failed_casts_are_ignored():
    m = scenario(3, n=1)
    # spam: a second press 2 ticks later should be ignored; a press without success too
    order(m, START + 3000 + 5, 0, 8, ability="item_black_king_bar")
    order(m, START + 9000, 0, 8, ability="item_black_king_bar")
    f = ReactionTimeHeuristic(CFG).run(m)[0]
    assert f.metrics["measured_reactions"] == 1


def test_invisible_attacker_is_not_a_trigger():
    m = scenario(3)
    set_vis(m, 6, START + 1, radiant=False, dire=True)  # Lion hidden from Radiant all game
    f = ReactionTimeHeuristic(CFG).run(m)[0]
    assert f.metrics["measured_reactions"] == 0


def test_poisson_tail():
    assert poisson_sf(0, 3.0) == 1.0
    assert abs(poisson_sf(1, 1.0) - (1 - 0.36787944)) < 1e-6
    assert poisson_sf(10, 1.0) < 1e-6
