"""Summaries of parsed CI job records.

usage: python3 -I summarize.py ci.jsonl ci_runs.tsv MODE
MODE jobs   : per run, every job (machine, exec, queue, outcome, top stages)
MODE stages : per run and machine, every verify stage with seconds
MODE top    : per run, the slowest jobs per machine
"""
import collections
import datetime as dt
import json
import re
import sys

recs = [json.loads(l) for l in open(sys.argv[1])]
runs = {}
for line in open(sys.argv[2]):
    f = line.rstrip('\n').split('\t')
    runs[f[1]] = dict(page=int(f[0]), sha=f[2], created=f[3], updated=f[4], concl=f[5], pr=f[6])
mode = sys.argv[3]
by_run = collections.defaultdict(list)
for r in recs:
    by_run[r['run']].append(r)


def machine(job):
    if 'aarch64' in job or 'ARM64' in job:
        return 'arm'
    return 'x86'


order = sorted(by_run, key=lambda k: runs.get(k, {}).get('created', ''))
for run in order:
    meta = runs.get(run, {})
    jobs = by_run[run]
    sha = next((j['sha'] for j in jobs if j['sha']), '?')
    print(f"## run {run} page {meta.get('page')} {meta.get('created', '')[:16]} #{meta.get('pr')} "
          f"{sha[:8]} {meta.get('concl')} jobs={len(jobs)}")
    if mode == 'jobs':
        for j in sorted(jobs, key=lambda j: (machine(j['job']), -j['exec_s'])):
            st = ' '.join(f"{n}={s:.0f}" for n, _, s in j['stages'] if not (n == 'bootstrap' and s < 5))
            print(f"  {machine(j['job'])} {j['job'][:44]:44} ex={j['exec_s']:7.1f} q={j['queue_s'] or 0:6.1f} "
                  f"{j['outcome']:9} {st[:120]}")
    elif mode == 'stages':
        agg = collections.defaultdict(float)
        for j in jobs:
            for n, _, s in j['stages']:
                if n == 'bootstrap' and s < 5:
                    continue
                agg[(machine(j['job']), n)] += s
        for (m, n), s in sorted(agg.items()):
            print(f"  {m} {n:28} {s:8.1f}")
    elif mode == 'top':
        for m in ('x86', 'arm'):
            js = sorted((j for j in jobs if machine(j['job']) == m), key=lambda j: -j['exec_s'])[:8]
            print(f"  {m}: " + ', '.join(f"{re.sub(r'^verify \\(|, (x86_64|aarch64)\\)$', '', j['job'])[:26]}"
                                         f"={j['exec_s'] / 60:.1f}{'!' if j['outcome'] != 'ok' else ''}" for j in js))
