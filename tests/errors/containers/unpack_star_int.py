# error: cannot unpack non-iterable int object
# (CPython: TypeError where it runs)
a, *b = 5
print(a, b)
