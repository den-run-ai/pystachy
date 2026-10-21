# error: cannot infer the type of 'types', an empty set so far
# lib/statistics's mean() stays uncompiled (lib/README.md): _sum() adds the data exactly, as
# fractions.Fraction (which Pystachy does not have), and keeps the data's types, which are classes,
# in a set
import statistics

print(statistics.mean([1.0, 2.0, 4.0]))
