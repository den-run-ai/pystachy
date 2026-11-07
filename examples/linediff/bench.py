"""bench: linediff.py under CPython and as a Pystachy AOT executable, in each mode, on two versions
of a generated text of 50,000 lines; the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The texts and the executable go to build/linediff/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "linediff")
    os.makedirs(out, exist_ok=True)
    texts = []
    for version in ["old", "new"]:
        path = os.path.join(out, f"{version}.txt")
        texts.append(path)
        if not os.path.exists(path):
            # (into a file of its own first: an interrupted run leaves no short text under this name)
            with open(path + ".part", "w") as f:
                run([sys.executable, "-I", os.path.join(here, "gentext.py"), "50000", version], stdout=f)
            os.replace(path + ".part", path)
    exe = os.path.join(out, "linediff_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "linediff.py"), "-o", exe])
    print(f"pystachy build linediff.py: {time.perf_counter() - t:.2f} s")
    prog = os.path.join(here, "linediff.py")

    print(f"{'mode':12} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for args in [[], ["--words"], ["-q"]]:
        c, a = measure_pair([[sys.executable, "-I", prog] + args + texts, [exe] + args + texts], runs, status=1)
        print(f"{' '.join(args) or 'unified':12} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
