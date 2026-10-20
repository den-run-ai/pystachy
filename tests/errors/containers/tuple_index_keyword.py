# error: tuple.index() takes no keyword arguments
# (CPython's TypeError, at compile time; also of a runtime-length tuple)
v = tuple([1, 2])
print(v.index(1, start=0))
