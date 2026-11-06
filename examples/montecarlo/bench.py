"""bench: montecarlo.py under CPython and as a Pystachy AOT executable, with 1 and 10 million
samples; the median wall and CPU (user + system) times of N runs, and whether both print the same
estimates. On a shared host, the CPU time varies less than the wall time.

usage: python3 -I bench.py PYSTACHY [N]
The executable goes to build/montecarlo/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "montecarlo")
    os.makedirs(out, exist_ok=True)
    prog = os.path.join(here, "montecarlo.py")
    exe = os.path.join(out, "montecarlo_aot")
    t = time.perf_counter()
    run([pys, "build", prog, "-o", exe])
    print(f"pystachy build montecarlo.py: {time.perf_counter() - t:.2f} s")

    print(f"{'samples':>10} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython CPU':>12} {'AOT CPU':>9} {'speedup':>8}")
    for n in [1000000, 10000000]:
        c, a = measure_pair([[sys.executable, "-I", prog, "42", str(n)], [exe, "42", str(n)]], runs, cpu=True, rss=False)
        print(f"{n:>10} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.cpu_s:11.3f}s {a.cpu_s:8.3f}s {c.cpu_s / a.cpu_s:7.1f}x")


if __name__ == "__main__":
    main()
