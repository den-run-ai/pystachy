from itertools import islice

print(list(islice(zip("abc", [1, 2, 3]), 2)))
