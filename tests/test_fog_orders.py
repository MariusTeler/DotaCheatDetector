from synth import START, make_match, order, set_vis

from dotacheat.config import load_config
from dotacheat.heuristics.fog_orders import FogOrdersHeuristic

CFG = load_config()


def run(m):
    return FogOrdersHeuristic(CFG).run(m)


def hide_dire_hero(m, pid, tick):
    """Dire hero *pid* disappears from Radiant's vision at *tick*."""
    set_vis(m, pid, tick, radiant=False, dire=True)


def test_attack_on_visible_enemy_is_fine():
    m = make_match()
    set_vis(m, 6, START, radiant=True, dire=True)
    order(m, START + 300, 0, 4, target_pid=6)
    r = run(m)[0]
    assert r.detections == [] and r.subscore == 0


def test_order_just_after_target_left_vision_is_latency():
    m = make_match()
    set_vis(m, 6, START, radiant=True, dire=True)
    hide_dire_hero(m, 6, START + 100)
    order(m, START + 100 + 8, 0, 4, target_pid=6, ping=60)  # 0.27 s later
    assert run(m)[0].detections == []


def test_repeated_orders_on_long_hidden_enemy_are_flagged():
    m = make_match(minutes=30)
    set_vis(m, 6, START, radiant=True, dire=True)
    hide_dire_hero(m, 6, START + 100)
    for k in range(4):  # 4 separate incidents, 10 s apart, target hidden for 5+ s
        order(m, START + 250 + k * 300, 0, 4, target_pid=6)
    r = run(m)[0]
    assert len(r.detections) == 4
    assert r.subscore > 0.5
    d = r.detections[0]
    assert d.clock == "00:08" and "ceață" in d.explanation and d.data["hidden_s"] > 4


def test_spam_on_same_hidden_target_counts_once():
    m = make_match()
    set_vis(m, 6, START, radiant=True, dire=True)
    hide_dire_hero(m, 6, START + 100)
    for k in range(20):
        order(m, START + 300 + k * 3, 0, 4, target_pid=6)
    assert len(run(m)[0].detections) == 1


def test_single_incident_does_not_score():
    m = make_match()
    set_vis(m, 6, START, radiant=True, dire=True)
    hide_dire_hero(m, 6, START + 100)
    order(m, START + 400, 0, 6, target_pid=6, ability="lion_voodoo")
    r = run(m)[0]
    assert len(r.detections) == 1 and r.subscore == 0


def test_rate_is_normalised_by_duration():
    def scored(minutes, n):
        m = make_match(minutes=minutes)
        set_vis(m, 6, START, radiant=True, dire=True)
        hide_dire_hero(m, 6, START + 100)
        for k in range(n):
            order(m, START + 300 + k * 600, 0, 4, target_pid=6)
        return run(m)[0].subscore
    assert abs(scored(30, 3) - scored(60, 6)) < 1e-9


def test_ally_targets_ignored_and_no_visibility_means_not_applicable():
    m = make_match()
    order(m, START + 300, 0, 4, target_pid=1)
    assert run(m)[0].detections == []
    m2 = make_match(visibility=False)
    assert run(m2)[0].applicable is False
