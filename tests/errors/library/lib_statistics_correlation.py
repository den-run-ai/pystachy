# error: expected list[int], got list[float] (compiling statistics.correlation(
# lib/statistics's correlation() compiles for floats (tests/programs/library/lib_statistics_correlation.py): of
# ints, it rebinds its parameters x and y, lists of ints, to the lists of float ranks or
# deviations, which a variable of one type cannot hold
import statistics

print(statistics.correlation([1, 2, 3], [1, 3, 2]))
