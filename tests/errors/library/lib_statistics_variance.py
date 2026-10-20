# error: cannot infer the type of 'types', an empty set so far
# lib/statistics's stdev(), and variance(), pvariance() and pstdev(), stay uncompiled
# (lib/README.md): _ss() sums the squares exactly, as fractions.Fraction (which Pystachy does not
# have), and keeps the data's types, which are classes, in a set
import statistics

print(statistics.stdev([1.0, 2.0, 4.0]))
