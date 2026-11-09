"""Parse GitHub Actions run-log archives into per-job timing records (JSON lines).

usage: python3 -I parse_logs.py OUT.jsonl ZIP...
Each ZIP is named <prefix>-<run_id>.zip. Records: run, sha, job, created, start, end,
queue_s, exec_s, outcome, steps [(label, start_offset_s, dur_s)], stages [(name, status, secs)].
"""
import datetime as dt
import json
import re
import sys
import zipfile

TS = re.compile(r'^\ufeff?(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)Z ?(.*)$')
STAGE = re.compile(r'^(\S+)\s+(pass|fail|FAIL|timeout|skip\S*|xfail)\s+([0-9.]+)s\s+(\S+)')
SHA = re.compile(r'^[0-9a-f]{40}$')


def ts(s):
    s = s[:26]  # microseconds at most
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()


def lines(text):
    out = []
    for raw in text.splitlines():
        m = TS.match(raw)
        if m:
            out.append((ts(m.group(1)), m.group(2)))
        elif out:
            out.append((out[-1][0], raw))
    return out


def parse_zip(path):
    run = re.search(r'-(\d+)\.zip$', path).group(1)
    z = zipfile.ZipFile(path)
    names = z.namelist()
    systems = {n.rsplit('/', 1)[0]: n for n in names if n.endswith('/system.txt')}
    tops = [n for n in names if '/' not in n and n.endswith('.txt')]
    jobs = {}
    for n in tops:
        job = re.sub(r'^\d+_', '', n)[:-4]
        jobs[job] = z.read(n).decode('utf-8', 'replace')
    if not tops:  # older layout: <job>/<step>_<name>.txt
        per = {}
        for n in names:
            if '/' in n and not n.endswith('system.txt'):
                job, step = n.split('/', 1)
                m = re.match(r'(\d+)_', step)
                per.setdefault(job, []).append((int(m.group(1)) if m else 0, n))
        for job, steps in per.items():
            jobs[job] = '\n'.join(z.read(n).decode('utf-8', 'replace') for _, n in sorted(steps))
    recs = []
    for job, text in jobs.items():
        L = lines(text)
        if not L:
            continue
        sysL = lines(z.read(systems[job]).decode('utf-8', 'replace')) if job in systems else []
        created = min((t for t, _ in sysL), default=None)
        about = [t for t, s in sysL if s.startswith('Job is about to start running')]
        start = L[0][0]
        end = L[-1][0]
        sha = None
        for i, (t, s) in enumerate(L):
            if s.startswith('[command]/usr/bin/git log -1 --format=%H') and i + 1 < len(L):
                cand = L[i + 1][1].strip()
                if SHA.match(cand):
                    sha = cand
                    break
        steps, stages, errors = [], [], []
        cur = None
        for t, s in L:
            if s.startswith('##[group]Run '):
                if cur:
                    steps.append((cur[0], round(cur[1] - start, 1), round(t - cur[1], 1)))
                cur = (s[13:90], t)
            m = STAGE.match(s)
            if m:
                stages.append((m.group(1), m.group(2), float(m.group(3))))
            if s.startswith('##[error]'):
                errors.append(s[9:200])
        if cur:
            steps.append((cur[0], round(cur[1] - start, 1), round(end - cur[1], 1)))
        outcome = 'ok'
        joined = ' | '.join(errors)
        if 'maximum execution time' in joined:
            outcome = 'timeout'
        elif 'operation was canceled' in joined.lower() or 'was cancelled' in joined.lower():
            outcome = 'cancelled'
        elif errors:
            outcome = 'error'
        img = next((s.split(':', 1)[1].strip() for t, s in L[:40] if s.startswith('Version: 2')), None)
        recs.append(dict(run=run, sha=sha, job=job, created=created, start=start, end=end,
                         queue_s=round(start - created, 1) if created else None,
                         about=about[0] if about else None,
                         exec_s=round(end - start, 1), outcome=outcome, errors=errors[:4],
                         steps=steps, stages=stages, image=img))
    return recs


def main():
    out = open(sys.argv[1], 'w')
    for p in sys.argv[2:]:
        try:
            for r in parse_zip(p):
                out.write(json.dumps(r) + '\n')
        except Exception as e:  # keep going; report
            print(f'{p}: {e!r}', file=sys.stderr)


if __name__ == '__main__':
    main()
