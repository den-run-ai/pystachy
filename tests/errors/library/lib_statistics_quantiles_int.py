# error: quantiles() returns both list[float | int] and list[int]
# lib/statistics's quantiles() of ints (lib/README.md): CPython returns n - 1 copies of one data
# point, ints, and interpolates floats between two or more: the fresh list[int] of the first
# return (data * (n - 1)) is not converted to the list[float | int] that the others give.
import statistics

print(statistics.quantiles([1, 3, 2, 4], n=4))
