# A library raising the recursion limit for a bounded deep recursion, then restoring it
import sys


def depth(n: int) -> int:
    if n == 0:
        return 0
    return 1 + depth(n - 1)


def guarded(n: int) -> int:
    old = sys.getrecursionlimit()
    if old < 10000:
        sys.setrecursionlimit(10000)
    try:
        return depth(n)
    finally:
        if old < 10000:
            sys.setrecursionlimit(old)


print(sys.getrecursionlimit(), guarded(5000), sys.getrecursionlimit())
try:
    depth(5000)
except RecursionError:
    print("RecursionError at the default limit")
