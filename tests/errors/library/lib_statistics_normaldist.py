# error: class statistics.NormalDist is not supported
# lib/statistics's NormalDist stays uncompiled (lib/README.md): it has properties, reflected
# operators and a __slots__ dict, and statistics imports random, for samples(), in CPython only
import statistics

print(statistics.NormalDist(1.0, 2.0).cdf(1.5))
