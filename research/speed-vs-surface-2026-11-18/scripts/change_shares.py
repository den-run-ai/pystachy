"""Share of changed lines by area in periods of main's first-parent history (git only).

usage: python3 change_shares.py REPO REF OUT.json
Counts added + deleted lines of every first-parent merge's diff against its first parent.
Periods: 7-19 October, 20 October to the 12 November report (main 8434a911), and since then.
"""
import collections, datetime, json, re, subprocess, sys


def area(p):
    if p.startswith('src/') or p == 'pystachy.py': return 'compiler'
    if p in ('runtime.c', 'runtime.py', 'pyembed.c', 'pyext.c', 'lljit.c') or p.startswith(('ryu/', 'mpz/')): return 'runtime'
    if p.startswith('lib/'): return 'library'
    if p.startswith('tests/'): return 'tests'
    if 'lean' in p: return 'lean proofs'
    if p.startswith('docs/') or p.endswith('.md'): return 'docs'
    if p.startswith(('tools/', '.github/', 'Makefile')): return 'tools/CI'
    if p.startswith(('bench/', 'examples/')): return 'bench/examples'
    if p.startswith('ports/'): return 'ports'
    return 'other'


repo, ref, out = sys.argv[1:]
log = subprocess.run(['git', '-C', repo, 'log', '--first-parent', '-m', '--numstat', '--format=@%ct %H', ref],
                     capture_output=True, text=True, check=True).stdout
utc = datetime.timezone.utc
cut1 = int(datetime.datetime(2026, 10, 20, tzinfo=utc).timestamp())
report = int(subprocess.run(['git', '-C', repo, 'log', '-1', '--format=%ct', '8434a911'], capture_output=True, text=True).stdout)
names = ['7-19 Oct', '20 Oct-11 Nov (to 8434a911)', '12-17 Nov (after 8434a911)']
per = {k: collections.Counter() for k in names}
t = None
for line in log.splitlines():
    if line.startswith('@'):
        t = int(line[1:].split()[0])
        continue
    m = re.match(r'(\d+)\t(\d+)\t(.*)', line)
    if m and t:
        k = names[0] if t < cut1 else names[1] if t <= report else names[2]
        per[k][area(m.group(3))] += int(m.group(1)) + int(m.group(2))
res = {}
for k, c in per.items():
    tot = sum(c.values())
    res[k] = {"total": tot, "share": {a: round(v / tot, 4) for a, v in c.most_common()}, "lines": dict(c)}
    print(f'{k}: {tot:,} lines changed:', ', '.join(f'{a} {v / tot:.0%}' for a, v in c.most_common()))
json.dump(res, open(out, 'w'), indent=1)
