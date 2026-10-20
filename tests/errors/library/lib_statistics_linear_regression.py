# error: expected list[float], got Generator[float]
# lib/statistics's linear_regression() stays uncompiled (lib/README.md): it binds its parameter y, a
# list, to a generator expression (a variable has one type), and its result is a
# collections.namedtuple (Pystachy has no collections)
import statistics

print(statistics.linear_regression([1.0, 2.0, 3.0], [1.0, 3.0, 2.0]))
