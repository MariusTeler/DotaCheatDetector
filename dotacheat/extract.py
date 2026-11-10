"""Single-pass replay extraction on top of gem-dota.

gem gives us players, combat log, the game clock and — crucially — the
authoritative per-team visibility bitsets (``m_bNPCVisibleState`` of the
``CDOTA_DataRadiant/Dire`` entities). On top of that we hook three things gem
does not expose publicly:

* ``DOTA_UM_SpectatorPlayerUnitOrders`` — every order each player sent, with
  target, position, ability, ping and latency;
* hero positions at tick resolution;
* ``CDOTAPlayerController.m_iCursor`` (raw cursor values) and ability/item entity
  names (so ``ability_index`` in orders can be resolved to e.g. ``item_blink``).

Nothing here talks to a Dota 2 client: the input is only a ``.dem`` file.
"""

from __future__ import annotations

import collections
import gzip
import logging
import pickle
from pathlib import Path

from . import __version__
from .model import (
    CombatEvent,
    MatchData,
    Order,
    Player,
    Track,
    VisEvent,
    CAST_ORDERS,
)

log = logging.getLogger(__name__)

CACHE_FORMAT = 3  # bump when MatchData layout or extraction semantics change
WORLD_OFFSET = 16384.0  # cell * 128 + vec - 16384 => world coordinates


def _state(value: object) -> int:
    s = str(value).upper()
    if "VISIBLE" in s:
        return 1
    if "HIDDEN" in s:
        return 0
    return -1


def parse_replay(path: str | Path) -> MatchData:
    """Parse *path* (a .dem file) into :class:`MatchData`. Takes ~1 min per match."""
    import gem
    import gem.parser
    from gem.proto import dota_usermessages_pb2 as um
    from gem.state.entities import EntityOp

    path = Path(path)
    unit_order_id = um.DOTA_UM_SpectatorPlayerUnitOrders
    raw_orders: list[tuple[int, bytes]] = []
    hero_pos: dict[int, Track] = collections.defaultdict(Track)
    cursor: dict[int, Track] = collections.defaultdict(Track)
    ability_names: dict[int, list[tuple[int, str]]] = collections.defaultdict(list)
    hero_entities: set[int] = set()
    controller_pid: dict[int, int] = {}

    base = gem.parser.ReplayParser

    class _Parser(base):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._on_entity_filtered(self._hero, class_prefixes=("CDOTA_Unit_Hero_",))
            self._on_entity_filtered(self._controller, class_names=("CDOTAPlayerController",))
            self._on_entity_fields(self._ability, required_fields=("m_fCooldown",),
                                   changed_fields=("m_pEntity.m_nameStringableIndex",))

        def _entity_name(self, e) -> str | None:
            names = self.string_tables.get_by_name("EntityNames")
            if names is None:
                return None
            for f in ("m_pEntity.m_nameStringableIndex", "m_pEntity.m_nameStringTableIndex"):
                try:
                    idx = e.get(f)
                except Exception:  # field absent in this build
                    idx = None
                if idx is not None and idx >= 0:
                    item = names.items.get(idx)
                    if item is not None and item[0]:
                        return item[0]
            return None

        def _hero(self, e, op):
            if op.has(EntityOp.DELETED):
                return
            cx = e.get("CBodyComponent.m_cellX")
            if cx is None:
                return
            idx = e.get_index()
            hero_entities.add(idx)
            hero_pos[idx].add(
                self.tick,
                cx * 128 + e.get("CBodyComponent.m_vecX") - WORLD_OFFSET,
                e.get("CBodyComponent.m_cellY") * 128 + e.get("CBodyComponent.m_vecY") - WORLD_OFFSET,
            )

        def _controller(self, e, op):
            if op.has(EntityOp.DELETED):
                return
            idx = e.get_index()
            pid = e.get("m_nPlayerID")
            if pid is not None and pid >= 0:
                controller_pid[idx] = pid
            c0, c1 = e.get("m_iCursor.0000"), e.get("m_iCursor.0001")
            if c0 is not None and c1 is not None:
                cursor[idx].add(self.tick, float(c0), float(c1))

        def _ability(self, e, op):
            if op.has(EntityOp.DELETED):
                return
            name = self._entity_name(e)
            if not name:
                return
            lst = ability_names[e.get_index()]
            if not lst or lst[-1][1] != name:
                lst.append((self.tick, name))

        def _dispatch_inner(self, type_id, payload):
            if type_id == unit_order_id:
                raw_orders.append((self.tick, payload))
            super()._dispatch_inner(type_id, payload)

    gem.parser.ReplayParser = _Parser
    try:
        match = gem.parse(str(path))
    finally:
        gem.parser.ReplayParser = base

    # ---- players & heroes -------------------------------------------------
    hero_index_by_pid: dict[int, int] = {}
    for ev in match.hero_visibility_events:
        hero_index_by_pid.setdefault(ev.player_id, ev.entity_index)
    players = []
    for p in match.players:
        players.append(Player(pid=p.player_id, team=p.team, hero=p.hero_name or "?",
                              name=p.player_name or "", account_id=p.account_id or 0,
                              hero_index=hero_index_by_pid.get(p.player_id, -1)))
    pid_by_hero_index = {v: k for k, v in hero_index_by_pid.items()}

    # ---- orders ---------------------------------------------------------
    def resolve_ability(index: int, tick: int) -> str:
        lst = ability_names.get(index)
        if not lst:
            return ""
        name = lst[0][1]
        for t, n in lst:
            if t > tick:
                break
            name = n
        return name

    decoded = []
    vote: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for tick, payload in raw_orders:
        m = um.CDOTAUserMsg_SpectatorPlayerUnitOrders()
        m.ParseFromString(payload)
        decoded.append((tick, m))
        for u in m.units:
            if u in pid_by_hero_index:
                vote[m.entindex][pid_by_hero_index[u]] += 1
    orderer: dict[int, int] = {}
    for ent, c in vote.items():
        orderer[ent] = c.most_common(1)[0][0]
    for ent, pid in controller_pid.items():
        orderer.setdefault(ent, pid if pid < 10 else pid // 2)

    orders: list[Order] = []
    for tick, m in decoded:
        pid = orderer.get(m.entindex)
        if pid is None:
            continue
        ability = resolve_ability(m.ability_id, tick) if m.order_type in CAST_ORDERS else ""
        orders.append(Order(
            tick=tick, pid=pid, order_type=m.order_type, units=tuple(m.units),
            target_index=m.target_index, ability_index=m.ability_id,
            x=m.position.x, y=m.position.y, queue=m.queue,
            ping_ms=m.ping, latency_ms=m.last_order_latency, ability=ability))

    # ---- combat log -----------------------------------------------------
    combat = []
    for e in match.combat_log:
        t = str(e.log_type)
        t = t.split(".")[-1].split(":")[0].strip("<> '")
        combat.append(CombatEvent(
            tick=e.tick, type=t, attacker=e.attacker_name or "", target=e.target_name or "",
            inflictor=e.inflictor_name or "", attacker_illusion=bool(e.attacker_is_illusion),
            target_illusion=bool(e.target_is_illusion), value=int(e.value or 0),
            stun_duration=float(e.stun_duration or 0.0)))

    # ---- visibility -----------------------------------------------------
    visibility: dict[int, list[VisEvent]] = collections.defaultdict(list)
    known = 0
    for ev in match.entity_visibility_events:
        r, d = _state(ev.radiant_state), _state(ev.dire_state)
        known += (r >= 0) + (d >= 0)
        visibility[ev.entity_index].append(VisEvent(
            tick=ev.tick, serial=ev.entity_serial, name=ev.npc_name, team=ev.team,
            active=ev.active, radiant=r, dire=d))

    clock = match.game_clock
    pauses = []
    if clock is not None:
        for pz in getattr(clock, "pauses", []) or []:
            pauses.append((pz.start_tick, pz.end_tick))

    hero_tracks = {pid: hero_pos[idx] for pid, idx in hero_index_by_pid.items() if idx in hero_pos}
    cursor_tracks = {orderer[ent]: tr for ent, tr in cursor.items() if ent in orderer}
    illusions = hero_entities - set(hero_index_by_pid.values())

    try:
        from importlib.metadata import version
        gem_version = version("gem-dota")
    except Exception:
        gem_version = "?"

    return MatchData(
        match_id=int(match.match_id or 0), source=str(path),
        game_start_tick=int(match.game_start_tick or 0),
        game_end_tick=int(match.post_game_tick or match.game_end_tick or 0),
        players=players, orders=orders, combat=combat, hero_tracks=hero_tracks,
        cursor_tracks=cursor_tracks, visibility=dict(visibility),
        hero_index_by_pid=hero_index_by_pid, illusion_indices=illusions, pauses=pauses,
        has_visibility=known > 0,
        parser_version=f"dotacheat {__version__} / gem-dota {gem_version}",
    )


def load_or_parse(path: str | Path, cache_dir: str | Path | None = None) -> MatchData:
    """Parse with an on-disk cache keyed on file name, size and mtime."""
    path = Path(path)
    if cache_dir is None:
        return parse_replay(path)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    st = path.stat()
    key = cache_dir / f"{path.stem}.{st.st_size}.{int(st.st_mtime)}.v{CACHE_FORMAT}.mdata.gz"
    if key.exists():
        try:
            with gzip.open(key, "rb") as fh:
                return pickle.load(fh)
        except Exception as exc:  # corrupt cache: re-parse
            log.warning("ignoring unreadable cache %s: %s", key, exc)
    data = parse_replay(path)
    with gzip.open(key, "wb", compresslevel=3) as fh:
        pickle.dump(data, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return data
