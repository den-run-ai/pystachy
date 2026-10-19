# error: unsupported call sum(list[float | int])
# sum() of a list of int | float items is not supported yet (CPython adds ints exactly until
# the first float, then floats with a compensated sum).
print(sum([2.5, 1]))
