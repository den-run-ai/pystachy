# error: each function is a type of its own
# Bounded match now lowers its kernel selection, but distinct lambda values still
# cannot share one inferred native function slot; function __doc__ writes also remain unsupported.
import statistics

print(statistics.kde([1.0, 2.0, 4.0], h=1.5)(2.0))
