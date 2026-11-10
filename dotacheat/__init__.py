"""Post-match Dota 2 replay analyzer that estimates cheat *suspicion* (never a verdict).

The tool works exclusively on replay files after the match. It never reads the
memory of, injects into, or otherwise interacts with a running Dota 2 client.
"""

__version__ = "0.1.0"
TICKS_PER_SECOND = 30
