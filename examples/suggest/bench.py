"""bench: suggest.py under CPython and as a Pystachy AOT executable, for a generated vocabulary of
20,000 words and texts of 25 and 100 lines; the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The vocabulary, the texts and the executable go to build/suggest/ of the checkout.
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
    out = os.path.join(here, "..", "..", "build", "suggest")
    os.makedirs(out, exist_ok=True)

    def generate(name: str, args: list[str]) -> str:
        path = os.path.join(out, name)
        if not os.path.exists(path):
            # (into a file of its own first: an interrupted run leaves no short file under this name)
            with open(path + ".part", "w") as f:
                run([sys.executable, "-I", os.path.join(here, "genvocab.py")] + args, stdout=f)
            os.replace(path + ".part", path)
        return path

    vocab = generate("vocab.txt", ["vocab", "20000"])
    texts = [generate("text25.txt", ["text", "20000", "25"]), generate("text100.txt", ["text", "20000", "100"])]
    exe = os.path.join(out, "suggest_aot")
    t = time.perf_counter()
    run([pys, "build", os.path.join(here, "suggest.py"), "-o", exe])
    print(f"pystachy build suggest.py: {time.perf_counter() - t:.2f} s")
    prog = os.path.join(here, "suggest.py")

    print(f"{'text':10} {'unknown':>8} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for text in texts:
        c, a = measure_pair([[sys.executable, "-I", prog, vocab, text], [exe, vocab, text]], runs, status=1)
        unknown = c.stdout.decode().splitlines()[-1].split()[0]
        print(f"{os.path.basename(text):10} {unknown:>8} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
