import pickle, bisect, collections, statistics
d = pickle.load(open('d855.pkl','rb'))
team = {h: t for _, h, t in d['players']}
hv = collections.defaultdict(list)
for tick, pid, h, idx, r, di in d['hv']: hv[h].append((tick, r, di))
def timeline(h, t):  # list of (tick, visible bool) for team t
    return [(tk, 'VISIBLE' in (r if t == 2 else di).upper()) for tk, r, di in hv[h]]
def state(tl, tick):
    i = bisect.bisect_right([x[0] for x in tl], tick) - 1
    return None if i < 0 else tl[i][1]
def dist_to_visible(tl, tick):
    best = 10**9
    for j, (tk, v) in enumerate(tl):
        if v:
            end = tl[j+1][0] if j+1 < len(tl) else 10**9
            if tk <= tick < end: return 0
            best = min(best, abs(tk - tick), abs(end - tick))
    return best
ds = []; byinfl = collections.Counter(); bypair = collections.Counter()
for tick, lt, a, tg, infl, ai, ti, vr, vd, val in d['cl']:
    if not lt.endswith('DAMAGE') or a not in team or tg not in team or ai or ti or team[a] == team[tg]: continue
    tl = timeline(tg, team[a])
    if state(tl, tick) is False:
        ds.append(dist_to_visible(tl, tick)); byinfl[infl or 'attack'] += 1; bypair[(a[14:], tg[14:])] += 1
print('n', len(ds), 'median ticks to visible', statistics.median(ds), 'quantiles', statistics.quantiles(ds, n=10))
print(collections.Counter(min(x//15, 20) for x in ds).most_common())
print(byinfl.most_common(15)); print(bypair.most_common(10))
# visibility transitions rate
for h in list(hv)[:3]: print(h, len(hv[h]), hv[h][:6])
