# lib/random.py's real-valued and discrete distributions against CPython's, value for value over
# several seeds: uniform(), triangular() (with and without mode, reversed bounds, low == high),
# normalvariate(), gauss() and its saved second value, lognormvariate(), expovariate(),
# vonmisesvariate(), gammavariate() (alpha below, at and above 1), betavariate(), paretovariate(),
# weibullvariate() and binomialvariate() on its three paths (n == 1, the geometric method and BTRS,
# whose test uses the port of math.lgamma()) up to n near 2**63, on Random objects and the module's
# functions, with their errors, and the lgamma port (math.lgamma in CPython) at quarter-integers,
# where C's round() differs from Python's, and past 64-bit ints
import math
import random
from random import Random


def show(label: str, values: list[float]) -> None:
    print(label, values)


for s in [0, 1, 2, -77, 123456789, 9223372036854775807]:
    print("seed", s)
    r = Random(s)
    show("uniform", [r.uniform(0.0, 1.0), r.uniform(-5.0, 5.0), r.uniform(3.0, 1.0),
                     r.uniform(2.0, 2.0), r.uniform(1e300, -1e300)])
    show("triangular", [r.triangular(), r.triangular(0.0, 10.0), r.triangular(0.0, 10.0, 9.0),
                        r.triangular(10.0, 0.0, 1.0), r.triangular(-1.0, 1.0, -1.0),
                        r.triangular(4.0, 4.0, 4.0)])
    show("normalvariate", [r.normalvariate() for i in range(4)]
         + [r.normalvariate(100.0, 15.0), r.normalvariate(-3.0, 0.001)])
    show("gauss", [r.gauss() for i in range(5)] + [r.gauss(10.0, 2.0), r.gauss(sigma=0.5)])
    show("lognormvariate", [r.lognormvariate(0.0, 1.0), r.lognormvariate(1.5, 0.25),
                            r.lognormvariate(-2.0, 3.0)])
    show("expovariate", [r.expovariate(), r.expovariate(0.1), r.expovariate(25.0),
                         r.expovariate(-2.0)])
    show("vonmisesvariate", [r.vonmisesvariate(0.0, 0.0), r.vonmisesvariate(1.0, 1e-7),
                             r.vonmisesvariate(3.0, 0.5), r.vonmisesvariate(math.pi, 8.0),
                             r.vonmisesvariate(6.0, 100.0)])
    show("gammavariate", [r.gammavariate(0.2, 1.0), r.gammavariate(0.9, 3.0),
                          r.gammavariate(1.0, 2.0), r.gammavariate(1.5, 1.0),
                          r.gammavariate(9.0, 0.5), r.gammavariate(1000.0, 1.0)])
    show("betavariate", [r.betavariate(0.5, 0.5), r.betavariate(2.0, 5.0), r.betavariate(1.0, 1.0),
                         r.betavariate(30.0, 0.3)])
    show("paretovariate", [r.paretovariate(1.0), r.paretovariate(3.5), r.paretovariate(0.2)])
    show("weibullvariate", [r.weibullvariate(1.0, 1.0), r.weibullvariate(2.0, 0.5),
                            r.weibullvariate(0.5, 4.0)])
    print("binomialvariate", [r.binomialvariate() for i in range(8)],
          [r.binomialvariate(1, 0.9) for i in range(4)],
          [r.binomialvariate(20, 0.25) for i in range(6)],
          [r.binomialvariate(30, 0.02) for i in range(4)])
    print("binomialvariate", [r.binomialvariate(100, 0.4) for i in range(6)],
          [r.binomialvariate(1000, 0.75) for i in range(4)],
          [r.binomialvariate(10**6, 0.5) for i in range(3)], r.binomialvariate(10**12, 0.3),
          r.binomialvariate(0, 0.5), r.binomialvariate(7, 0.0), r.binomialvariate(7, 1.0))

print("many draws")
r = Random(31337)
for name in ["gauss", "normalvariate", "gammavariate", "betavariate", "vonmisesvariate"]:
    values: list[float] = []
    for i in range(2000):
        if name == "gauss":
            values.append(r.gauss(1.0, 2.0))
        elif name == "normalvariate":
            values.append(r.normalvariate(1.0, 2.0))
        elif name == "gammavariate":
            values.append(r.gammavariate(0.5 + i % 7, 1.5))
        elif name == "betavariate":
            values.append(r.betavariate(0.25 + i % 5, 2.0))
        else:
            values.append(r.vonmisesvariate(1.0, 0.5 + i % 3))
    print(name, math.fsum(values), min(values), max(values), values[1999])
draws = [r.binomialvariate(50 + i % 40, 0.3 + (i % 9) / 20) for i in range(3000)]
print("binomial", sum(draws), min(draws), max(draws), draws[-5:])

print("binomialvariate near 2**63")
M = 9223372036854775807
print([Random(s).binomialvariate(M - 1, 2e-18) for s in [0, 1, 2]],
      [Random(s).binomialvariate(M - 1, 0.5) for s in [0, 1]],
      Random(5).binomialvariate(M - 1, 0.75))

print("lgamma")
for x in [-0.25, -0.75, -1.25, -2.25, -3.25, -2.75, -1.5, -4.5, 0.5, 2.5, -1.4999999999999998,
          0.49999999999999994, 1e-25, -1e-25, 1.0, 2.0, 3.0, 1e20, 1e300, 2.0**63, 1e306, 0.0, -1.0,
          -1e20, -1e300, -2.0**63, math.inf, -math.inf]:
    try:
        print(x, random._lgamma(x))
    except (ValueError, OverflowError) as e:
        print(x, type(e).__name__, e)
print(math.isnan(random._lgamma(math.nan)), random._lgamma(7))

print("gauss's second value")
r = Random(8)
first = r.gauss()
second = r.gauss()
r.seed(8)
print(first == r.gauss(), r.getstate()[2] == second, r.gauss() == second, r.getstate()[2])
r.gauss()
r.seed(8)
print(r.getstate()[2], r.gauss() == first)
state = r.getstate()
a = r.gauss()
r.setstate(state)
print(a == r.gauss() == second)

print("module functions")
random.seed(2718)
print(random.uniform(1.0, 2.0), random.triangular(0.0, 1.0, 0.25), random.normalvariate(0.0, 1.0),
      random.gauss(0.0, 1.0), random.lognormvariate(0.0, 0.5), random.expovariate(3.0))
print(random.vonmisesvariate(0.0, 4.0), random.gammavariate(2.0, 2.0), random.betavariate(2.0, 2.0),
      random.paretovariate(2.0), random.weibullvariate(1.0, 1.5), random.binomialvariate(40, 0.5))


def attempt(label: str, f) -> None:
    try:
        print(label, f())
    except (ValueError, ZeroDivisionError, AssertionError) as e:
        print(label, type(e).__name__, e)


print("errors")
r = Random(1)
attempt("gammavariate(0, 1)", lambda: r.gammavariate(0.0, 1.0))
attempt("gammavariate(1, -1)", lambda: r.gammavariate(1.0, -1.0))
attempt("betavariate(0, 1)", lambda: r.betavariate(0.0, 1.0))
attempt("binomialvariate(-1)", lambda: r.binomialvariate(-1, 0.5))
attempt("binomialvariate(p=1.5)", lambda: r.binomialvariate(5, 1.5))
attempt("binomialvariate(p=-0.5)", lambda: r.binomialvariate(5, -0.5))
attempt("binomialvariate(p=nan)", lambda: r.binomialvariate(5, float("nan")))
attempt("expovariate(0)", lambda: r.expovariate(0.0))
attempt("paretovariate(0)", lambda: r.paretovariate(0.0))
attempt("weibullvariate(1, 0)", lambda: r.weibullvariate(1.0, 0.0))
attempt("lognormvariate(0, -1)", lambda: r.lognormvariate(0.0, -1.0))
