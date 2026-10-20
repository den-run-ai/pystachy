# a bool looks up an int-keyed dict as the int it is (True is the key 1)
d: dict[int, int] = {1: 10, 2: 20}
print(True in d, False in d, d[True])
