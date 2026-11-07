"""bench: cut.py under CPython and as a Pystachy AOT executable, for four selections of a generated
table of 500,000 lines (about 30 MB); the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The table and the executable go to build/cut/ of the checkout.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from example_bench import measure_pair, positive_int, run


def main() -> None:
    pys = sys.argv[1]
    runs = positive_int(sys.argv[2]) if len(sys.argv) > 2 else 5
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "..", "build", "cut")
    os.makedirs(out, exist_ok=True)
    table = os.path.join(out, "table.tsv")
    if not os.path.exists(table):
        # (into a file of its own first: an interrupted run leaves no short table under this name)
        with open(table + ".part", "w") as f:
            run([sys.executable, "-I", os.path.join(here, "gentable.py"), "500000"], stdout=f)
        os.replace(table + ".part", table)
    exe = os.path.join(out, "cut_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "cut.py"), "-o", exe])
    print(f"pystachy build cut.py: {time.perf_counter() - t:.2f} s")
    cut = os.path.join(here, "cut.py")

    print(f"{'selection':28} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for args in [["-f", "2,5-7"], ["-f", "3", "--complement"], ["-c", "1-20"], ["-s", "-f", "8,1"]]:
        c, a = measure_pair([[sys.executable, "-I", cut] + args + [table], [exe] + args + [table]], runs)
        print(f"{' '.join(args):28} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
