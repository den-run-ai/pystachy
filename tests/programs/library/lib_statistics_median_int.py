# lib/statistics's median() of ints: CPython returns the middle int of an odd number of them,
# and the mean of the two middle ones, a float, of an even number: int | float.
import statistics

print(statistics.median([1, 3, 2]), statistics.median([1, 3, 2, 4]))
