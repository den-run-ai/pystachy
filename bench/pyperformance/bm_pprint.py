"""Test the performance of pprint.PrettyPrinter.

This benchmark was available as `python -m pprint` until Python 3.12.

Authors: Fred Drake (original), Oleg Iarygin (pyperformance port).
"""

# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.
from pprint import PrettyPrinter


printable = [('string', (1, 2), [3, 4], {5: 6, 7: 8})] * 100_000
p = PrettyPrinter()


if __name__ == '__main__':
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops and argv[2] the number of items printed, upstream's 100,000
    # by default. Each of upstream's two bench_func() calls is one timed loop; the
    # lengths, flags and a digest of the results are printed, and the time goes to
    # stderr.
    import hashlib
    import sys
    import time
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    size = int(sys.argv[2]) if len(sys.argv) > 2 else len(printable)
    data = printable[:size]
    seconds = 0.0
    t0 = time.perf_counter()
    for _ in range(loops):
        safe = p._safe_repr(data, {}, None, 0)
    seconds += time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(loops):
        text = p.pformat(data)
    seconds += time.perf_counter() - t0
    print("seconds", seconds, file=sys.stderr)
    print("pprint", loops, size, len(safe[0]), safe[1], safe[2], hashlib.md5(safe[0].encode()).hexdigest(),
          len(text), hashlib.md5(text.encode()).hexdigest())
    print(text[:160])
