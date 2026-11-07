"""bench: mazepath.py under CPython and as a Pystachy AOT executable, on generated mazes of
1001 x 1001 and 2001 x 2001 cells; the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The mazes and the executable go to build/mazepath/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "mazepath")
    os.makedirs(out, exist_ok=True)
    mazes = []
    for size in [1001, 2001]:
        path = os.path.join(out, f"maze{size}.txt")
        mazes.append(path)
        if not os.path.exists(path):
            # (into a file of its own first: an interrupted run leaves no short maze under this name)
            with open(path + ".part", "w") as f:
                run([sys.executable, "-I", os.path.join(here, "genmaze.py"), str(size), str(size)], stdout=f)
            os.replace(path + ".part", path)
    exe = os.path.join(out, "mazepath_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "mazepath.py"), "-o", exe])
    print(f"pystachy build mazepath.py: {time.perf_counter() - t:.2f} s")
    prog = os.path.join(here, "mazepath.py")

    print(f"{'maze':14} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for maze in mazes:
        c, a = measure_pair([[sys.executable, "-I", prog, maze], [exe, maze]], runs)
        print(f"{os.path.basename(maze):14} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
