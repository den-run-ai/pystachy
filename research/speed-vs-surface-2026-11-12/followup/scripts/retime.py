"""Quiet, interleaved, pinned re-timing of selected AOT executables (and CPython) for one benchmark.

usage: python3.13 -I retime.py BENCH REPS OUT.json LABEL...
Each repetition runs CPython and every label's executable in an order rotated by one position,
pinned to CPU 3; output must equal CPython's. Ports report their 'seconds' line, micro wall time.
"""
import json, re, statistics, subprocess, sys, time
from pathlib import Path
S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
bench, reps, out, labels = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4:]
spec = json.load(open(S / "sweep/perf_specs.json"))[bench]
ref = json.load(open(S / "sweep/cpython_ref.json"))["ref"][bench]["stdout"]
root = S / "sweep/perfroot"
cmds = {"cpython": ["/usr/local/bin/python3.13", "-I", str(root / spec["src"])] + spec["args"]}
for lab in labels:
    cmds[lab] = [str(S / "exe" / lab / bench)] + spec["args"]
names = list(cmds)
samples = {n: [] for n in names}
for r in range(reps):
    order = names[r % len(names):] + names[:r % len(names)]
    for n in order:
        t0 = time.perf_counter()
        p = subprocess.run(["taskset", "-c", "3"] + cmds[n], cwd=root, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        assert p.returncode == 0 and p.stdout == ref, (n, p.stdout[-200:], p.stderr[-200:])
        found = re.findall(r"^seconds (\S+)$", p.stderr, re.M)
        samples[n].append(float(found[0]) if len(found) == 1 else wall)
res = {n: {"median_ms": round(statistics.median(v) * 1000, 2), "min_ms": round(min(v) * 1000, 2),
           "max_ms": round(max(v) * 1000, 2), "samples": v} for n, v in samples.items()}
json.dump({"bench": bench, "reps": reps, "cpu": 3, "metric": "seconds line" if spec["kind"] == "pyperformance" else "process wall",
           "results": res}, open(out, "w"), indent=1)
for n in names:
    print(f"{bench:12s} {n:22s} median {res[n]['median_ms']:8.2f} ms  range {res[n]['min_ms']:.2f}-{res[n]['max_ms']:.2f}")
