# error: dict keys must be int or str
# lib/statistics's mode() of floats (lib/README.md): it counts them in a dict, as
# collections.Counter does, and a dict of Pystachy has no float keys
import statistics

print(statistics.mode([1.5, 2.5, 1.5]))
