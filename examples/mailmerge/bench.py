"""bench: mailmerge.py under CPython and as a Pystachy AOT executable, in each mode, on 100,000
generated records: the median wall time of N runs, the peak RSS of one, and whether the mailboxes
are the same.

usage: python3 -I bench.py PYSTACHY [N]
The data and the executable go to build/mailmerge/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "mailmerge")
    os.makedirs(out, exist_ok=True)
    data = os.path.join(out, "data_100k.tsv")
    if not os.path.exists(data):
        # (into a file of its own first: an interrupted run leaves no short file under this name)
        with open(data + ".part", "w") as f:
            run([sys.executable, "-I", os.path.join(here, "gendata.py"), "100000"], stdout=f)
        os.replace(data + ".part", data)
    exe = os.path.join(out, "mailmerge_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "mailmerge.py"), "-o", exe])
    print(f"pystachy build mailmerge.py: {time.perf_counter() - t:.2f} s")
    template = os.path.join(here, "notice.txt")
    mailmerge = os.path.join(here, "mailmerge.py")

    print(f"{'mode':12} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for mode in ["", "--safe", "--split"]:
        extra = [mode] if mode else []
        c, a = measure_pair([[sys.executable, "-I", mailmerge, template, data] + extra, [exe, template, data] + extra],
                            runs, expected_stderr=b"mailmerge: 100000 messages\n")
        print(f"{mode or 'substitute':12} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.2f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
