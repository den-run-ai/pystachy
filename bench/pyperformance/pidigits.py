# coding: utf-8
# pystachy: python-int
# Pystachy port: the module opts in to promoting ints (docs/python-int.md); the
# digits need CPython's arbitrary-precision int, not checked 64-bit ints.
"""
Calculating some of the digits of π.

This benchmark stresses big integer arithmetic.

Adapted from code on:
http://benchmarksgame.alioth.debian.org/
"""

import itertools

# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.


DEFAULT_DIGITS = 2000
icount = itertools.count
islice = itertools.islice


def gen_x():
    # Pystachy port: a generator expression for map(lambda k: ..., icount(1)), equally
    # lazy; map() is supported only where its items are taken at once.
    return ((k, 4 * k + 2, 0, 2 * k + 1) for k in icount(1))


def compose(a, b):
    aq, ar, as_, at = a
    bq, br, bs, bt = b
    return (aq * bq,
            aq * br + ar * bt,
            as_ * bq + at * bs,
            as_ * br + at * bt)


def extract(z, j):
    q, r, s, t = z
    return (q * j + r) // (s * j + t)


def gen_pi_digits():
    z = (1, 0, 0, 1)
    x = gen_x()
    while 1:
        y = extract(z, 3)
        while y != extract(z, 4):
            z = compose(z, next(x))
            y = extract(z, 3)
        z = compose((10, -10 * y, 0, 1), z)
        yield y


def calc_ndigits(n):
    return list(islice(gen_pi_digits(), n))


def add_cmdline_args(cmd, args):
    cmd.extend(("--digits", str(args.digits)))


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops, argv[2] the number of digits (upstream's --digits); every
    # digit is printed, and the time goes to stderr.
    import sys
    import time
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ndigits = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DIGITS
    t0 = time.perf_counter()
    for _ in range(loops):
        digits = calc_ndigits(ndigits)
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    print("pidigits", loops, ndigits, len(digits))
    print("".join([str(d) for d in digits]))
