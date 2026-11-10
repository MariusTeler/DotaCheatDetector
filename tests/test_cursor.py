import random

from synth import START, make_match, move, order, set_vis

from dotacheat.config import load_config
from dotacheat.heuristics.cursor import CursorHeuristic

CFG = load_config()


def world(cam, c):
    x, y = c[0] / 510 - 0.5, c[1] / 383 - 0.5
    return cam[0] + 2500 * x, cam[1] - 1700 * y


def build(cheat: bool, n=40, seed=4):
    """Player 0 clicks around with a steady camera; every 3 s attacks Lion (pid 6)."""
    rnd = random.Random(seed)
    m = make_match(minutes=40)
    set_vis(m, 6, START, radiant=True, dire=True)
    tr = m.cursor_tracks[0]
    t = START + 300
    for k in range(n):
        cam = (rnd.uniform(-5000, 5000), rnd.uniform(-5000, 5000))
        for j in range(8):  # pairs of quick move clicks: calibration + anchors
            c = (rnd.uniform(60, 450), rnd.uniform(40, 250))
            tr.add(t, *c)
            order(m, t, 0, 1, x=world(cam, c)[0], y=world(cam, c)[1])
            t += 3
        c = (rnd.uniform(100, 400), rnd.uniform(60, 240))
        tr.add(t, *c)
        lion = world(cam, c)
        if cheat:
            lion = (lion[0] + 4000, lion[1])  # Lion is far from the cursor
        move(m, 6, t - 1, *lion)
        order(m, t, 0, 4, target_pid=6)
        t += 3
        c2 = (rnd.uniform(60, 450), rnd.uniform(40, 250))
        tr.add(t, *c2)
        order(m, t, 0, 1, x=world(cam, c2)[0], y=world(cam, c2)[1])
        t += 90
    return m


def test_honest_clicks_are_under_the_cursor():
    f = CursorHeuristic(CFG).run(build(False))[0]
    assert f.applicable and f.metrics["fit_residual"] < 50
    assert f.metrics["checked_orders"] >= 30 and f.metrics["far_orders"] == 0


def test_orders_far_from_cursor_are_flagged():
    f = CursorHeuristic(CFG).run(build(True))[0]
    assert f.metrics["far_orders"] >= 30 and f.subscore > 0.9


def test_without_cursor_data_not_applicable():
    m = make_match()
    assert CursorHeuristic(CFG).run(m)[0].applicable is False
