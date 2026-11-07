"""bench: latency.py under CPython and as a Pystachy AOT executable, on generated logs of 1,000,000
and 4,000,000 requests: the median wall time of N runs (process start-up included), the medians of
the times the runs report for reading the log and for the statistics (--time), and the peak RSS of
one run; and whether CPython and the executable print the same report.

usage: python3 -I bench.py PYSTACHY [N]
The logs and the executable go to build/latency/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "latency")
    os.makedirs(out, exist_ok=True)
    logs = []
    for n in [1000000, 4000000]:
        path = os.path.join(out, f"log_{n // 1000000}m.txt")
        logs.append(path)
        if not os.path.exists(path):
            # (into a file of its own first: an interrupted run leaves no short log under this name)
            with open(path + ".part", "w") as f:
                run([sys.executable, "-I", os.path.join(here, "genlog.py"), str(n)], stdout=f)
            os.replace(path + ".part", path)
    exe = os.path.join(out, "latency_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "latency.py"), "-o", exe])
    print(f"pystachy build latency.py: {time.perf_counter() - t:.2f} s")
    program = os.path.join(here, "latency.py")

    print(f"{'log':4} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'read CPython':>13} {'read AOT':>9}"
          f" {'stats CPython':>14} {'stats AOT':>10} {'CPython RSS':>12} {'AOT RSS':>9}")
    for log in logs:
        cpython = [sys.executable, "-I", program, log]
        aot = [exe, log]
        commands = [cpython, aot]
        c, a = measure_pair(commands, runs, timed_commands=[cmd + ["--time"] for cmd in commands],
                            timing_labels=("read", "statistics"))
        name = os.path.basename(log)[4:-4]
        print(f"{name:4} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.2f}x {c.timings['read']:12.3f}s {a.timings['read']:8.3f}s"
              f" {c.timings['statistics']:13.3f}s {a.timings['statistics']:9.3f}s {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
