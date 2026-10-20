# Running out of memory ends the program as an uncaught MemoryError does in CPython: what it
# printed before is written, stderr's last line is "MemoryError" and the status 1. (Pystachy's
# except clauses do not catch it: docs/language/compatibility.md.) The size is decided at run
# time: 2 ** 61 bytes, which no allocator gives.
import sys

n = len(sys.argv) + 2 ** 60
words = ["kept", "in", "a", "buffer"]
print(" ".join(words), end=" ")
print(len(words))
s = "ab" * n
print("not reached", len(s))
