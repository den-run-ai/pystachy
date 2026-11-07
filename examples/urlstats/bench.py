"""bench: urlstats.py under CPython and as a Pystachy AOT executable, on generated logs of 200,000 and
1,000,000 requests, making the report and printing each request's canonical URL (--canon): the
median wall time of N runs, process start-up included, the median of the times the runs report for
reading the log (--time), and the peak RSS of one run; and whether the two print the same.

usage: python3 -I bench.py PYSTACHY [N]
The logs and the executable go to build/urlstats/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "urlstats")
    os.makedirs(out, exist_ok=True)
    logs = []
    for n in [200000, 1000000]:
        path = os.path.join(out, f"log_{n // 1000}k.txt" if n < 1000000 else f"log_{n // 1000000}m.txt")
        logs.append(path)
        if not os.path.exists(path):
            # (into a file of its own first: an interrupted run leaves no short log under this name)
            with open(path + ".part", "w") as f:
                run([sys.executable, "-I", os.path.join(here, "genlog.py"), str(n)], stdout=f)
            os.replace(path + ".part", path)
    exe = os.path.join(out, "urlstats_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "urlstats.py"), "-o", exe])
    print(f"pystachy build urlstats.py: {time.perf_counter() - t:.2f} s")
    prog = os.path.join(here, "urlstats.py")

    print(f"{'log':5} {'mode':7} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'read CPython':>13} {'read AOT':>9} {'CPython RSS':>12} {'AOT RSS':>9}")
    for log in logs:
        for mode in ["", "--canon"]:
            args = ([mode] if mode else []) + [log]
            commands = [[sys.executable, "-I", prog] + args, [exe] + args]
            timed = [[sys.executable, "-I", prog, "--time"] + args, [exe, "--time"] + args]
            c, a = measure_pair(commands, runs, timed_commands=timed,
                                timing_labels=("read", "report"), zero_ok=("report",))
            name = os.path.basename(log)[4:-4]
            print(f"{name:5} {mode or 'report':7} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.2f}x {c.timings['read']:12.3f}s {a.timings['read']:8.3f}s {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
