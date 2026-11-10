import sys, time, collections, bisect
import gem, gem.parser
from gem.parser import ReplayParser
from gem.proto import dota_usermessages_pb2 as um
UO = um.DOTA_UM_SpectatorPlayerUnitOrders
orders = []; cursor = collections.defaultdict(list); hero_pos = collections.defaultdict(list)
class P(ReplayParser):
    def __init__(s, *a, **k):
        super().__init__(*a, **k)
        s.on_entity(s._spy)
    def _spy(s, e, op):
        cn = e.get_class_name()
        if cn == 'CDOTAPlayerController':
            c = (e.get('m_iCursor.0000'), e.get('m_iCursor.0001'))
            l = cursor[e.get_index()]
            if not l or l[-1][1] != c: l.append((s.tick, c))
        elif cn.startswith('CDOTA_Unit_Hero_'):
            x = e.get('CBodyComponent.m_cellX'); 
            if x is None: return
            pos = (x*128+e.get('CBodyComponent.m_vecX')-16384, e.get('CBodyComponent.m_cellY')*128+e.get('CBodyComponent.m_vecY')-16384)
            l = hero_pos[e.get_index()]
            if not l or l[-1][1] != pos: l.append((s.tick, pos))
    def _dispatch_inner(s, t, payload):
        if t == UO:
            m = um.CDOTAUserMsg_SpectatorPlayerUnitOrders(); m.ParseFromString(payload); orders.append((s.tick, m))
        super()._dispatch_inner(t, payload)
gem.parser.ReplayParser = P
t0 = time.time(); match = gem.parse(sys.argv[1]); print('full gem.parse seconds', round(time.time()-t0,1))
print('match', match.match_id, 'start tick', match.game_start_tick, 'end', match.game_end_tick)
hero_by_idx = {}
for pl in match.players: print(pl.player_id, pl.hero_name, pl.team, pl.player_name)
vis = collections.defaultdict(list)
for ev in match.entity_visibility_events: vis[ev.entity_index].append(ev)
print('entity vis events', len(match.entity_visibility_events), 'hero vis events', len(match.hero_visibility_events))
hv = collections.defaultdict(list)
for ev in match.hero_visibility_events: hv[ev.entity_index].append(ev); hero_by_idx[ev.entity_index] = (ev.player_id, ev.hero_name)
print('hero entity idx', hero_by_idx)
names = {v: k for k, v in __import__('gem.proto.dota_shared_enums_pb2', fromlist=['x']).dotaunitorder_t.items()} if hasattr(__import__('gem.proto.dota_shared_enums_pb2', fromlist=['x']), 'dotaunitorder_t') else {}
oc = collections.Counter(m.order_type for _, m in orders); print('order types', [(names.get(k,k), v) for k, v in oc.most_common(25)])
# map orderer entindex -> hero via units
ctrl = collections.defaultdict(collections.Counter)
for _, m in orders:
    for u in m.units:
        if u in hero_by_idx: ctrl[m.entindex][hero_by_idx[u]] += 1
print('orderer entindex -> hero', {k: v.most_common(1) for k, v in sorted(ctrl.items())})
def state_at(evs, tick, team):
    i = bisect.bisect_right([e.tick for e in evs], tick) - 1
    if i < 0: return 'NO_DATA'
    e = evs[i]; return str(e.radiant_state if team == 2 else e.dire_state)
team_of = {pl.player_id: pl.team for pl in match.players}
res = collections.Counter(); samples = []
for tick, m in orders:
    if m.target_index in hero_by_idx and m.order_type in (4, 6):  # attack target / cast target
        orderer = ctrl[m.entindex].most_common(1)
        if not orderer: continue
        pid = orderer[0][0][0]; tgt_pid = hero_by_idx[m.target_index][0]
        if team_of[pid] == team_of[tgt_pid]: res['ally'] += 1; continue
        s = state_at(hv[m.target_index], tick, team_of[pid]); res[s] += 1
        if 'HIDDEN' in s and len(samples) < 15: samples.append((tick, (tick - match.game_start_tick)/30, pid, hero_by_idx[m.target_index], m.order_type, m.ability_id))
print('enemy-hero targeted orders by target visibility:', res)
for s in samples: print('  hidden-target order', s)
print('cursor changes per controller', {k: len(v) for k, v in cursor.items()}, list(cursor.values())[0][:5] if cursor else None)
print('hero pos samples per hero', {k: len(v) for k, v in hero_pos.items()})
print('ABILITY/ITEM log sample', [ (e.tick, e.attacker_name, e.inflictor_name, e.target_name) for e in match.combat_log if str(e.log_type).endswith('ITEM')][:5])
print('pings', sorted(m.ping for _, m in orders)[len(orders)//2], 'latency median', sorted(m.last_order_latency for _, m in orders)[len(orders)//2])
print('--- hidden-target details: ticks since target last visible to orderer team, ping, latency')
for tick, m in orders:
    if m.target_index in hero_by_idx and m.order_type in (4, 6):
        o = ctrl[m.entindex].most_common(1)
        if not o: continue
        pid = o[0][0][0]; team = team_of[pid]
        if team == team_of[hero_by_idx[m.target_index][0]]: continue
        evs = hv[m.target_index]
        if 'HIDDEN' not in state_at(evs, tick, team).upper(): continue
        last_vis = max([e.tick for e in evs if e.tick <= tick and 'VISIBLE' in str(e.radiant_state if team==2 else e.dire_state).upper()] or [-1])
        print(f'  t={(tick-match.game_start_tick)/30:7.1f}s pid={pid} tgt={hero_by_idx[m.target_index][1][14:]} type={m.order_type} abil={m.ability_id} since_vis={tick-last_vis} ticks ping={m.ping} lat={m.last_order_latency} queue={m.queue}')
c = cursor[4]; print('cursor sample', c[5000:5008]); print('hero pos sample', hero_pos[334][5000:5004])
import pickle; pickle.dump({'orders':[(t,m.SerializeToString()) for t,m in orders]}, open('orders.pkl','wb'))
print('--- cross-validation: combat-log DAMAGE hero->hero visibility flag vs bitset')
agree = collections.Counter()
name_to_idx = {v[1]: k for k, v in hero_by_idx.items()}
pid_of_name = {v[1]: v[0] for v in hero_by_idx.values()}
for e in match.combat_log:
    if str(e.log_type).endswith('DAMAGE') and e.attacker_name in name_to_idx and e.target_name in name_to_idx and not e.target_is_illusion and not e.attacker_is_illusion:
        ateam = team_of[pid_of_name[e.attacker_name]]
        if ateam == team_of[pid_of_name[e.target_name]]: continue
        flag = e.visible_radiant if ateam == 2 else e.visible_dire
        bit = state_at(hv[name_to_idx[e.target_name]], e.tick, ateam)
        agree[(flag, bit)] += 1
print(agree)
print('--- hidden attack orders followed by damage from orderer to target within 3s')
dmg = collections.defaultdict(list)
for e in match.combat_log:
    if str(e.log_type).endswith('DAMAGE'): dmg[(e.attacker_name, e.target_name)].append(e.tick)
n = hit = 0
for tick, m in orders:
    if m.target_index in hero_by_idx and m.order_type == 4:
        o = ctrl[m.entindex].most_common(1)
        if not o: continue
        pid, hname = o[0][0]; team = team_of[pid]
        if team == team_of[hero_by_idx[m.target_index][0]]: continue
        if 'HIDDEN' not in state_at(hv[m.target_index], tick, team).upper(): continue
        n += 1; ts = [t for t in dmg[(hname, hero_by_idx[m.target_index][1])] if tick <= t <= tick + 90]
        if ts: hit += 1; print('   damage after hidden order', (tick-match.game_start_tick)/30, hname, hero_by_idx[m.target_index][1], 'vis at dmg:', state_at(hv[m.target_index], ts[0], team))
print('hidden attack orders', n, 'followed by damage', hit)
