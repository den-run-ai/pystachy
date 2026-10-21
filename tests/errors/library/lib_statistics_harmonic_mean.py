# error: isinstance() is only supported with the builtin types and classes as its second argument
# lib/statistics's harmonic_mean() stays uncompiled (lib/README.md): past its iter(data) is data
# test, it checks isinstance(x, (numbers.Real, Decimal)) and sums exactly with _sum(), as
# fractions.Fraction
import statistics

print(statistics.harmonic_mean([40.0, 60.0]))
