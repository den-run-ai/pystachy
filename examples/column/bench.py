"""bench: column.py under CPython and as a Pystachy AOT executable, on a generated table of 300,000
lines (about 20 MB); the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The table and the executable go to build/column/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "column")
    os.makedirs(out, exist_ok=True)
    table = os.path.join(out, "table.tsv")
    if not os.path.exists(table):
        # (into a file of its own first: an interrupted run leaves no short table under this name)
        with open(table + ".part", "w") as f:
            run([sys.executable, "-I", os.path.join(here, "gentable.py"), "300000"], stdout=f)
        os.replace(table + ".part", table)
    exe = os.path.join(out, "column_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "column.py"), "-o", exe])
    print(f"pystachy build column.py: {time.perf_counter() - t:.2f} s")
    prog = os.path.join(here, "column.py")

    print(f"{'options':16} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for args in [[], ["-R", "1,5,6,7"], ["-o", " | "]]:
        c, a = measure_pair([[sys.executable, "-I", prog] + args + [table], [exe] + args + [table]], runs)
        print(f"{' '.join(args) or '(none)':16} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
