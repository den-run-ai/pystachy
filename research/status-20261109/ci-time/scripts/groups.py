"""Per-group job execution minutes since a date, split by runner class.

usage: python3 -I groups.py ci.jsonl ci_runs.tsv SINCE [UNTIL]
Runner class: arm; x86 'z3' when the bootstrap-restore stage took > 0.65 s (EPYC 7763
fingerprint, ~95% accurate against reported LLVM host CPUs), else x86 'fast'.
Columns: n, median and max execution minutes per class; outcomes other than ok are counted.
"""
import collections
import json
import re
import statistics as st
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from z3 import split_points  # noqa: E402

recs = [json.loads(l) for l in open(sys.argv[1])]
runs = {}
for line in open(sys.argv[2]):
    f = line.rstrip('\n').split('\t')
    runs[f[1]] = f
since = sys.argv[3]
until = sys.argv[4] if len(sys.argv) > 4 else '9999'
SP = split_points(recs)
data = collections.defaultdict(lambda: collections.defaultdict(list))
bad = collections.Counter()
for r in recs:
    created = runs[r['run']][3]
    if not (since <= created < until):
        continue
    m = re.match(r'verify \(([^,]+)(?:, (x86_64|aarch64))?\)$', r['job'])
    if not m:
        continue
    group, mach = m.group(1), m.group(2) or 'x86_64'
    rest = [s for n, _, s in r['stages'] if n == 'bootstrap' and s < 5]
    if mach == 'aarch64':
        cls = 'arm'
    else:
        cls = 'z3' if rest and rest[0] > SP.get(r['run'], 0.65) else 'fast'
    data[group][cls].append(r['exec_s'] / 60)
    if r['outcome'] != 'ok':
        bad[(group, cls, r['outcome'])] += 1


def fmt(v):
    if not v:
        return '      -        '
    return f"{len(v):2d} {st.median(v):5.1f} {max(v):5.1f}"


print('group'.ljust(20), 'z3: n med max    ', 'fast: n med max  ', 'arm: n med max')
for g in sorted(data, key=lambda g: -max(data[g].get('z3', [0]) + data[g].get('fast', [0]))):
    print(g.ljust(20), fmt(data[g]['z3']).ljust(18), fmt(data[g]['fast']).ljust(18), fmt(data[g]['arm']))
for k, v in sorted(bad.items()):
    print('non-ok:', k, v)
