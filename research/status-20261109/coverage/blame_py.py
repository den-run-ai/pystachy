import subprocess, sys, collections, json
repo = '/home/user/pystachy'
cov, rev, since = sys.argv[1], sys.argv[2], sys.argv[3]
unit = json.load(open(sys.argv[4]))['files'] if len(sys.argv) > 4 else {}
files = json.load(open(cov))['files']
mains = subprocess.run(['git', '-C', repo, 'log', '--first-parent', '--format=%H %s', f'{since}..{rev}'], capture_output=True, text=True).stdout.strip().split('\n')
mains = [m.split(' ', 1) for m in reversed(mains)]
cache = {}
def merge_of(c):
    if c in cache: return cache[c]
    r = 'before ' + since[:8]
    if subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', c, since]).returncode != 0:
        for h, s in mains:
            if subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', c, h]).returncode == 0:
                r = h[:8] + ' ' + s[:58]; break
    cache[c] = r
    return r
agg = collections.defaultdict(lambda: [0, 0, 0, 0])
for name, f in files.items():
    out = subprocess.run(['git', '-C', repo, 'blame', '--porcelain', rev, '--', name], capture_output=True, text=True).stdout
    lc = {}
    for l in out.split('\n'):
        p = l.split(' ')
        if len(p) >= 3 and len(p[0]) == 40 and all(c in '0123456789abcdef' for c in p[0]):
            lc[int(p[2])] = p[0]
    u = unit.get(name, {'executed_lines': [], 'executed_branches': []})
    ue = set(u['executed_lines']); ub = {tuple(b) for b in u['executed_branches']}
    for ln in f['missing_lines']:
        k = merge_of(lc[ln]); agg[k][0] += 1
        if ln not in ue: agg[k][2] += 1
    for b in f['missing_branches']:
        k = merge_of(lc[b[0]]); agg[k][1] += 1
        if tuple(b) not in ub: agg[k][3] += 1
for k, v in sorted(agg.items(), key=lambda kv: -kv[1][0]):
    print(f"{v[0]:4d} stmts {v[1]:4d} br | with unit tests {v[2]:4d} stmts {v[3]:4d} br  {k}")
