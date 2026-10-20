# sum(), min(), max() and sorted() of lists whose displays join int and float items
# (list[float | int]): CPython adds the ints exactly until the first float, then the floats with a
# compensated sum, and orders an int and a float exactly.
print(sum([2.5, 1]))
xs = [1, 2, 2.5]
print(sum(xs), sum(xs, 0.5), min(xs), max(xs), sorted(xs, reverse=True))
