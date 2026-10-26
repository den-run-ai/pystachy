"""Interleaved, CPU-pinned medians of #901's bench/integers workloads: CPython, and the
explicit-mpz variant built against two runtimes. usage: runbench.py DIR SAMPLES VARIANT..."""
import statistics, subprocess, sys
d, samples, variants = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
ARGS = {k: v for k, v in {"dectext": "400000", "bigmul": "600", "factorial": "300", "fibadd": "150", "modpow": "3000",
        "arith128": "8000000", "cross64": "5000000", "containers": "1000000"}.items() if k in (sys.argv[4:] and __import__("os").environ.get("ONLY", "").split() or [k])}
py = d + "/../venv/bin/python"
for w, arg in ARGS.items():
    cmds = {"cpython": [py, "-I", f"{d}/{w}.py", arg]}
    for v in variants:
        cmds[v] = [f"{d}/{w}_{v}", arg]
    times = {k: [] for k in cmds}
    checks = {}
    for s in range(samples):
        order = list(cmds) if s % 2 == 0 else list(reversed(cmds))
        for k in order:
            out = subprocess.run(["taskset", "-c", "1"] + cmds[k], capture_output=True, text=True, check=True).stdout.split()
            checks.setdefault(k, out[0])
            assert checks[k] == out[0], (w, k)
            times[k].append(float(out[-1]))
    if len(set(checks.values())) != 1:
        print(w, "CHECKSUMS DIFFER", checks); continue
    med = {k: statistics.median(t) for k, t in times.items()}
    print(f"{w:11s} " + "  ".join(f"{k} {med[k]:.3f}s ({med['cpython'] / med[k]:.2f}x)" for k in med), flush=True)
