import json, sys
ci = json.load(open(sys.argv[1]))['files']
local = json.load(open(sys.argv[2]))['files']
tot = {'st': 0, 'stm': 0, 'br': 0, 'brm': 0, 'stm0': 0, 'brm0': 0}
rows = []
for name, f in ci.items():
    s = f['summary']
    st = s['num_statements']; br = s['num_branches']
    miss = set(f['missing_lines']); mbr = {tuple(b) for b in f['missing_branches']}
    l = local.get(name)
    if l:
        miss2 = miss - set(l['executed_lines']); mbr2 = mbr - {tuple(b) for b in l['executed_branches']}
    else:
        miss2, mbr2 = miss, mbr
    tot['st'] += st; tot['br'] += br; tot['stm0'] += len(miss); tot['brm0'] += len(mbr); tot['stm'] += len(miss2); tot['brm'] += len(mbr2)
    if len(miss) - len(miss2) or len(mbr) - len(mbr2):
        rows.append((name, st, len(miss), len(miss2), br, len(mbr), len(mbr2)))
for r in sorted(rows, key=lambda r: -(r[2]-r[3])):
    print(f"{r[0]:45s} stmts {r[1]:5d} missed {r[2]:4d} -> {r[3]:4d} | branches {r[4]:5d} missed {r[5]:4d} -> {r[6]:4d}")
pc = lambda c, t: f"{100.0*c/t:.1f}%"
print('statements', pc(tot['st']-tot['stm0'], tot['st']), '->', pc(tot['st']-tot['stm'], tot['st']), f"(missed {tot['stm0']} -> {tot['stm']})")
print('branches  ', pc(tot['br']-tot['brm0'], tot['br']), '->', pc(tot['br']-tot['brm'], tot['br']), f"(missed {tot['brm0']} -> {tot['brm']})")
