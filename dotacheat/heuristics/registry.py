"""All available heuristics, in report order."""

from __future__ import annotations

import importlib

_SPECS = [
    ("fog_orders", "FogOrdersHeuristic"),
    ("fog_reactions", "FogReactionsHeuristic"),
    ("reaction_time", "ReactionTimeHeuristic"),
    ("scripts", "ScriptHeuristic"),
    ("lasthits", "LastHitHeuristic"),
    ("dodges", "DodgeHeuristic"),
    ("cursor", "CursorHeuristic"),
]


def all_heuristics():
    out = []
    for mod, cls in _SPECS:
        try:
            m = importlib.import_module(f"{__package__}.{mod}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__package__}.{mod}":
                continue  # not implemented yet
            raise
        out.append(getattr(m, cls))
    return out
