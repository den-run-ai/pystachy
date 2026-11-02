"""
The Computer Language Benchmarks Game
http://benchmarksgame.alioth.debian.org/

Contributed by Sokolov Yura, modified by Tupteq.
"""

# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.


DEFAULT_ARG = 9


def fannkuch(n):
    count = list(range(1, n + 1))
    max_flips = 0
    m = n - 1
    r = n
    perm1 = list(range(n))
    perm = list(range(n))
    perm1_ins = perm1.insert
    perm1_pop = perm1.pop

    while 1:
        while r != 1:
            count[r - 1] = r
            r -= 1

        if perm1[0] != 0 and perm1[m] != m:
            perm = perm1[:]
            flips_count = 0
            k = perm[0]
            while k:
                perm[:k + 1] = perm[k::-1]
                flips_count += 1
                k = perm[0]

            if flips_count > max_flips:
                max_flips = flips_count

        while r != n:
            perm1_ins(r, perm1_pop(0))
            count[r] -= 1
            if count[r] > 0:
                break
            r += 1
        else:
            return max_flips


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of runs, argv[2] the size; the result is printed, and the time to stderr.
    import sys
    import time
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    arg = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_ARG
    t0 = time.perf_counter()
    for _ in range(loops):
        result = fannkuch(arg)
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    print("fannkuch", loops, arg, result)
