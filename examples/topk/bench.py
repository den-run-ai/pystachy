"""bench: topk.py under CPython and as a Pystachy AOT executable, picking with heapq (the default)
and by sorting (--sort), on generated texts of 1,000,000 and 4,000,000 words: the median wall time
of N runs, the medians of the times the runs report for picking (--time), and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The texts and the executable go to build/topk/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "topk")
    os.makedirs(out, exist_ok=True)
    texts = []
    for n in [1000000, 4000000]:
        path = os.path.join(out, f"text_{n // 1000000}m.txt")
        texts.append(path)
        if not os.path.exists(path):
            # (into a file of its own first: an interrupted run leaves no short text under this name)
            with open(path + ".part", "w") as f:
                run([sys.executable, "-I", os.path.join(here, "gentext.py"), str(n)], stdout=f)
            os.replace(path + ".part", path)
    exe = os.path.join(out, "topk_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "topk.py"), "-o", exe])
    print(f"pystachy build topk.py: {time.perf_counter() - t:.2f} s")
    topk = os.path.join(here, "topk.py")

    print(f"{'text':5} {'mode':6} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'pick CPython':>13} {'pick AOT':>9} {'CPython RSS':>12} {'AOT RSS':>9}")
    for text in texts:
        for mode in ["", "--sort"]:
            extra = [mode] if mode else []
            commands = [[sys.executable, "-I", topk, text] + extra, [exe, text] + extra]
            c, a = measure_pair(commands, runs, timed_commands=[cmd + ["--time"] for cmd in commands],
                                timing_labels=("count", "pick"))
            name = os.path.basename(text)[5:-4]
            print(f"{name:5} {mode or 'heap':6} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.2f}x {c.timings['pick']:12.3f}s {a.timings['pick']:8.3f}s {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
