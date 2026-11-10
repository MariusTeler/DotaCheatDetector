import sys, pickle, gem, gem.parser
from gem.parser import ReplayParser
from gem.proto import dota_usermessages_pb2 as um
UO = um.DOTA_UM_SpectatorPlayerUnitOrders
orders = []
class P(ReplayParser):
    def _dispatch_inner(s, t, payload):
        if t == UO: orders.append((s.tick, payload))
        super()._dispatch_inner(t, payload)
gem.parser.ReplayParser = P
m = gem.parse(sys.argv[1])
d = dict(orders=orders, start=m.game_start_tick, players=[(p.player_id, p.hero_name, p.team) for p in m.players],
  hv=[(e.tick, e.player_id, e.hero_name, e.entity_index, str(e.radiant_state), str(e.dire_state)) for e in m.hero_visibility_events],
  cl=[(e.tick, str(e.log_type), e.attacker_name, e.target_name, e.inflictor_name, e.attacker_is_illusion, e.target_is_illusion, e.visible_radiant, e.visible_dire, e.value) for e in m.combat_log])
pickle.dump(d, open(sys.argv[2], 'wb'))
