# error: 'list' object is not an iterator
xs = [1, 2]
print(next(xs))  # (CPython: TypeError; iter(xs) is its iterator)
