# error: expected int, got bool
# (CPython runs it: True is the key 1 of an int-keyed dict)
d: dict[int, int] = {1: 10, 2: 20}
print(True in d)
