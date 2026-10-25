# usage: rundyn.py ROUNDS AOT_BINARY DYNANY_BENCH_PY : runs tools/dynany_bench.py's modes, built and under
# CPython, interleaved, ROUNDS times, pinned to core 1; prints median build and process ms and CPython's
# time over the AOT build's
import statistics
import subprocess
import sys

rounds, aot, src = int(sys.argv[1]), sys.argv[2], sys.argv[3]
cases = [("typed", "1000000"), ("union", "1000000"), ("dyn", "1000000"), ("generic", "1000000"), ("graph", "2000")]
modes = {"aot": [aot], "cpython": [sys.executable, "-I", src]}
res: dict = {}
sums: dict = {}
for _ in range(rounds):
    for mode, n in cases:
        for m, cmd in modes.items():
            out = subprocess.run(["taskset", "-c", "1"] + cmd + [mode, n], capture_output=True, text=True, check=True).stdout.split()
            sums.setdefault(mode, set()).add(out[0])
            res.setdefault((m, mode), ([], []))[0].append(int(out[1]) / 1e6)
            res[(m, mode)][1].append(int(out[2]) / 1e6)
for mode, n in cases:
    a = [statistics.median(x) for x in res[("aot", mode)]]
    c = [statistics.median(x) for x in res[("cpython", mode)]]
    print(f"{mode:8s} N={n:>8s}  build aot {a[0]:6.1f} cpython {c[0]:6.1f} ms ({c[0] / a[0]:5.2f}x)"
          f"   process aot {a[1]:6.1f} cpython {c[1]:6.1f} ms ({c[1] / a[1]:5.2f}x)"
          f"  checksums {'agree' if len(sums[mode]) == 1 else 'DIFFER'}")
