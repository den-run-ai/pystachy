import sys, bisect
sys.path.insert(0, '.')
from lcov import parse
info, sf, srcpath = sys.argv[1], sys.argv[2], sys.argv[3]
names = sys.argv[4:]
f = parse(info)[sf]
src = open(srcpath).read().split('\n')
starts = sorted((n, name) for name, n in f['fn'].items())
keys = [s[0] for s in starts]
def owner(ln):
    i = bisect.bisect_right(keys, ln) - 1
    return starts[i][1] if i >= 0 else '(top)'
for name in names:
    print('=====', name, 'starts', f['fn'].get(name))
    lines = sorted(set([ln for ln in f['da'] if owner(ln) == name] + [ln for ln in f['br'] if owner(ln) == name]))
    for ln in lines:
        c = f['da'].get(ln, None)
        br = f['br'].get(ln, [])
        mark = ''
        if c == 0: mark = 'MISS'
        elif br and any(t == 0 for t in br): mark = 'br' + ''.join('+' if t else '-' for t in br)
        if mark:
            print(f"{ln:5d} {mark:8s} {src[ln-1][:140]}")
