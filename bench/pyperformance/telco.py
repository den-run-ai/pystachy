# coding: UTF-8
""" Telco Benchmark for measuring the performance of decimal calculations

- http://speleotrove.com/decimal/telco.html
- http://speleotrove.com/decimal/telcoSpec.html

A call type indicator, c, is set from the bottom (least significant) bit of the duration (hence c is 0 or 1).
A rate, r, is determined from the call type. Those calls with c=0 have a low r: 0.0013; the remainder (‘distance calls’) have a ‘premium’ r: 0.00894. (The rates are, very roughly, in Euros or dollarates per second.)
A price, p, for the call is then calculated (p=r*n). This is rounded to exactly 2 fractional digits using round-half-even (Banker’s round to nearest).
A basic tax, b, is calculated: b=p*0.0675 (6.75%). This is truncated to exactly 2 fractional digits (round-down), and the total basic tax variable is then incremented (sumB=sumB+b).
For distance calls: a distance tax, d, is calculated: d=p*0.0341 (3.41%). This is truncated to exactly 2 fractional digits (round-down), and then the total distance tax variable is incremented (sumD=sumD+d).
The total price, t, is calculated (t=p+b, and, if a distance call, t=t+d).
The total prices variable is incremented (sumT=sumT+t).
The total price, t, is converted to a string, s.

"""

from decimal import ROUND_HALF_EVEN, ROUND_DOWN, Decimal, getcontext, Context
import io
import os
from struct import unpack
import time  # Pystachy port: time.perf_counter() is pyperf.perf_counter()

TIMED: list[float] = []  # Pystachy port: the seconds of each timed part


# Pystachy port: there is no __file__; the main passes the data file's path.
def rel_path(*path):
    return os.path.join("bench", "pyperformance", *path)


def bench_telco(loops, filename):
    getcontext().rounding = ROUND_DOWN
    rates = list(map(Decimal, ('0.0013', '0.00894')))
    twodig = Decimal('0.01')
    Banker = Context(rounding=ROUND_HALF_EVEN)
    basictax = Decimal("0.0675")
    disttax = Decimal("0.0341")

    with open(filename, "rb") as infil:
        data = infil.read()

    inbuf = io.BytesIO(data)  # Pystachy port: a name of its own; infil is the file above
    outfil = io.StringIO()

    start = time.perf_counter()
    for _ in range(loops):
        inbuf.seek(0)  # Pystachy port: see inbuf

        sumT = Decimal("0")   # sum of total prices
        sumB = Decimal("0")   # sum of basic tax
        sumD = Decimal("0")   # sum of 'distance' tax

        for i in range(5000):
            datum = inbuf.read(8)
            # Pystachy port: upstream compares these bytes with the str '', which is never
            # equal; a bytes/str comparison is rejected, so its break is left out.
            n, =  unpack('>Q', datum)

            calltype = n & 1
            r = rates[calltype]

            p = Banker.quantize(r * n, twodig)

            b = p * basictax
            b = b.quantize(twodig)
            sumB += b

            t = p + b

            if calltype:
                d = p * disttax
                d = d.quantize(twodig)
                sumD += d
                t += d

            sumT += t
            print(t, file=outfil)

        outfil.seek(0)
        outfil.truncate()

    TIMED.append(time.perf_counter() - start)  # Pystachy port: the seconds, which upstream returns
    return sumT, sumB, sumD  # Pystachy port: the last loop's sums, for the check


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops and argv[2] the data file (bench/pyperformance/data/telco-bench.b
    # from the repository root by default); the sums are printed, and the time goes to
    # stderr.
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    filename = sys.argv[2] if len(sys.argv) > 2 else rel_path("data", "telco-bench.b")
    total, basic, distance = bench_telco(loops, filename)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("telco", loops, total, basic, distance)
