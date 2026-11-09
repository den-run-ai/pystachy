import subprocess, sys, collections
sys.path.insert(0, '.')
from lcov import parse
repo = '/home/user/pystachy'
info, sf, rev, since = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
f = parse(info)[sf]
missed_lines = {ln for ln, c in f['da'].items() if c == 0}
missed_br = {ln: sum(1 for t in tk if t == 0) for ln, tk in f['br'].items() if any(t == 0 for t in tk)}
out = subprocess.run(['git', '-C', repo, 'blame', '--porcelain', rev, '--', sf], capture_output=True, text=True).stdout
line_commit = {}
cur = None
for l in out.split('\n'):
    parts = l.split(' ')
    if len(parts) >= 3 and len(parts[0]) == 40 and all(c in '0123456789abcdef' for c in parts[0]):
        cur = parts[0]; line_commit[int(parts[2])] = cur
mains = subprocess.run(['git', '-C', repo, 'log', '--first-parent', '--format=%H %s', f'{since}..{rev}'], capture_output=True, text=True).stdout.strip().split('\n')
mains = [m.split(' ', 1) for m in reversed(mains)]
cache = {}
def merge_of(c):
    if c in cache: return cache[c]
    r = 'before ' + since[:8]
    if subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', c, since]).returncode != 0:
        for h, s in mains:
            if subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', c, h]).returncode == 0:
                r = h[:8] + ' ' + s[:60]; break
    cache[c] = r
    return r
agg = collections.defaultdict(lambda: [0, 0])
for ln in missed_lines:
    agg[merge_of(line_commit[ln])][0] += 1
for ln, n in missed_br.items():
    agg[merge_of(line_commit[ln])][1] += n
for k, v in sorted(agg.items(), key=lambda kv: -kv[1][1]):
    print(f"{v[0]:4d} lines {v[1]:4d} branches  {k}")
