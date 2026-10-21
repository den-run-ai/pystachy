# error: unpack_star_tuple_short.py:4: error: cannot unpack tuple[int] into 2 or more targets
# A tuple's length is known where it is compiled (CPython: ValueError: not enough values to
# unpack (expected at least 2, got 1), where it runs)
a, *b, c = (1,)
print(a, b, c)
