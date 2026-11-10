"""One module per heuristic. Each exposes a ``Heuristic`` subclass; see ``registry``."""

from .base import Detection, Heuristic, PlayerFinding, saturate  # noqa: F401
