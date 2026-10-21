# error: generator values cannot be compared or printed
# itertools' functions return generators (lib/compatibility.md), which print as
# <generator object ...> where CPython prints count(5)
from itertools import count

print(count(5))
