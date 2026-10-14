"""Paired CPU timings for textwrap.wrap and fill on the same inputs.

usage: python3 tools/textwrap_pair_bench.py
       pystachy build tools/textwrap_pair_bench.py -o textwrap_pair_bench
       ./textwrap_pair_bench

Nine rounds alternate which operation runs first for each paragraph. Each round makes
1,000 calls to each operation, then measures joining precomputed wrapped lines separately.
Warm-up and equality checks are outside the timed regions. Timer overhead is included;
CPU time excludes scheduling waits but does not eliminate shared-host variability.
Checksum 21212190 must match CPython. Compare raw rounds, not just separate medians.
"""
import time
from textwrap import fill, wrap

from re_bench import inputs


def main() -> None:
    paras, _blocks = inputs(200)
    lines = [wrap(text, 70) for text in paras]
    for text in paras:
        assert fill(text, 70) == "\n".join(wrap(text, 70))
    check = 0
    for round_id in range(9):
        wrap_time = 0.0
        fill_time = 0.0
        for _ in range(5):
            for i in range(len(paras)):
                text = paras[i]
                if (i + round_id) % 2 == 0:
                    start = time.process_time()
                    w = wrap(text, 70)
                    wrap_time += time.process_time() - start
                    start = time.process_time()
                    f = fill(text, 70)
                    fill_time += time.process_time() - start
                else:
                    start = time.process_time()
                    f = fill(text, 70)
                    fill_time += time.process_time() - start
                    start = time.process_time()
                    w = wrap(text, 70)
                    wrap_time += time.process_time() - start
                check += len(w) + len(f)
        start = time.process_time()
        for _ in range(20):
            for parts in lines:
                check += len("\n".join(parts))
        join_time = time.process_time() - start
        print("round", round_id, "wrap_us", wrap_time * 1000, "fill_us", fill_time * 1000,
              "ratio", fill_time / wrap_time, "join_us", join_time * 250)
    print("checksum", check)


if __name__ == "__main__":
    main()
