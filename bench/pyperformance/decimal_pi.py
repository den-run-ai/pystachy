"""
Calculate `pi` using the decimal module.

The `pidigits` benchmark does a similar thing using regular (long) ints.

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


def pi_decimal():
    """decimal"""
    D = decimal.Decimal
    lasts, t, s, n, na, d, da = D(0), D(3), D(3), D(1), D(0), D(0), D(24)
    while s != lasts:
        lasts = s
        n, na = n + na, na + 8
        d, da = d + da, da + 32
        t = (t * n) / d
        s += t
    return s


def bench_decimal_pi():
    for prec in [9, 19]:
        decimal.getcontext().prec = prec
        for _ in range(10000):
            res = pi_decimal()  # Pystachy port: a variable of its own; _ holds the loop's int


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops; pi at both precisions is printed, and the time goes to stderr.
    import sys
    import time
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    t0 = time.perf_counter()
    for _ in range(loops):
        bench_decimal_pi()
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    digits = []
    for prec in [9, 19]:
        decimal.getcontext().prec = prec
        digits.append(str(pi_decimal()))
    print("decimal_pi", loops, digits)
