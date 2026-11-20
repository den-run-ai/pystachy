"""
Calculate `factorial` using the decimal module.

- 2024-06-14: Michael Droettboom copied this from
  Modules/_decimal/tests/bench.py in the CPython source and adapted to use
  pyperf.
"""

# Original copyright notice in CPython source:

#
# Copyright (C) 2001-2012 Python Software Foundation. All Rights Reserved.
# Modified and extended by Stefan Krah.
#


import decimal


# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.


# Pystachy port: the return type is annotated; a function that calls itself before
# it returns needs one.
def factorial(n, m) -> int | decimal.Decimal:
    if n > m:
        return factorial(m, n)
    elif m == 0:
        return 1
    elif n == m:
        return n
    else:
        return factorial(n, (n + m) // 2) * factorial((n + m) // 2 + 1, m)


# Pystachy port: upstream's sizes, which the main replaces for a smaller run.
SIZES = [10000, 100000]


def bench_decimal_factorial():
    c = decimal.getcontext()
    c.prec = decimal.MAX_PREC
    c.Emax = decimal.MAX_EMAX
    c.Emin = decimal.MIN_EMIN

    for n in SIZES:  # Pystachy port: [10000, 100000] by default; see SIZES
        # C version of decimal
        _ = factorial(decimal.Decimal(n), 0)


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops and the other arguments replace upstream's sizes; the digits
    # of each factorial are counted and two of its remainders printed, and the time goes to stderr.
    import sys
    import time
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if len(sys.argv) > 2:
        SIZES = [int(arg) for arg in sys.argv[2:]]
    t0 = time.perf_counter()
    for _ in range(loops):
        bench_decimal_factorial()
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    for size in SIZES:
        value = factorial(decimal.Decimal(size), 0) + decimal.Decimal(0)  # (a Decimal, also where factorial() is an int)
        print("decimal_factorial", loops, size, value.adjusted() + 1, value % 1000000007, value % 998244353)
