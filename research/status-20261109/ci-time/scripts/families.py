"""Family totals of verify stages per run.

usage: python3 -I families.py ci.jsonl ci_runs.tsv MACHINE [znver3|fast|all]
MACHINE x86 or arm. For x86, 'znver3' keeps only jobs whose bootstrap-restore stage
took > 0.65 s (EPYC 7763 fingerprint), 'fast' the others. Prints minutes per family
(sum over shards) and, in brackets, the number of shards contributing.
"""
import collections
import json
import re
import sys

recs = [json.loads(l) for l in open(sys.argv[1])]
runs = {}
for line in open(sys.argv[2]):
    f = line.rstrip('\n').split('\t')
    runs[f[1]] = f
want = sys.argv[3]
sel = sys.argv[4] if len(sys.argv) > 4 else 'all'


def machine(job):
    return 'arm' if ('aarch64' in job or 'ARM64' in job) else 'x86'


tab = collections.defaultdict(lambda: collections.defaultdict(float))
cnt = collections.defaultdict(lambda: collections.defaultdict(int))
for r in recs:
    if machine(r['job']) != want:
        continue
    rest = [s for n, _, s in r['stages'] if n == 'bootstrap' and s < 5]
    if sel != 'all' and want == 'x86':
        if not rest:
            continue
        slow = rest[0] > 0.65
        if (sel == 'znver3') != slow:
            continue
    for n, _, s in r['stages']:
        if n == 'bootstrap' and s < 5:
            continue
        f = re.sub(r'-\d+$', '', n)
        tab[r['run']][f] += s
        cnt[r['run']][f] += 1
order = sorted(tab, key=lambda k: runs[k][3])
fams = sorted({f for t in tab.values() for f in t})
print('family'.ljust(18) + ''.join(runs[k][3][5:10].rjust(9) for k in order))
print('pr'.ljust(18) + ''.join(('#' + runs[k][6]).rjust(9) for k in order))
for f in fams:
    row = ''
    for k in order:
        row += (f"{tab[k][f] / 60:6.1f}[{cnt[k][f]}]" if f in tab[k] else '        -').rjust(9)
    print(f[:18].ljust(18) + row)
