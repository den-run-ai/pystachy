import json, sys
ci = json.load(open(sys.argv[1]))['files']
locs = [json.load(open(p))['files'] for p in sys.argv[2:]]
st = br = stm0 = brm0 = stm = brm = 0
for name, f in ci.items():
    s = f['summary']
    miss = set(f['missing_lines']); mbr = {tuple(b) for b in f['missing_branches']}
    m2, b2 = set(miss), set(mbr)
    for l in locs:
        if name in l:
            m2 -= set(l[name]['executed_lines']); b2 -= {tuple(b) for b in l[name]['executed_branches']}
    st += s['num_statements']; br += s['num_branches']; stm0 += len(miss); brm0 += len(mbr); stm += len(m2); brm += len(b2)
    if name.endswith(('reflection.py', 'dynamic.py')):
        print(name, 'missed', len(miss), '->', len(m2), 'branches', len(mbr), '->', len(b2))
pc = lambda c, t: f"{100.0 * c / t:.1f}%"
print('statements', pc(st - stm0, st), '->', pc(st - stm, st), f'(missed {stm0} -> {stm})')
print('branches  ', pc(br - brm0, br), '->', pc(br - brm, br), f'(missed {brm0} -> {brm})')
