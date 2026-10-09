# A module whose code raises before it ends, its first two runs (tests/exc_import_retry.py)
from mods import counter

N = counter.incr(1)
print("half runs", N)
A = 1
B = int("x" if N < 3 else "2")
C = 3
