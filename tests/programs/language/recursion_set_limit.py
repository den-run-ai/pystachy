# Argument validation and rejection below the current active depth (#988).
import sys


def lower(n: int) -> bool:
    if n > 0:
        return lower(n - 1)
    before = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(5)
    except RecursionError:
        return sys.getrecursionlimit() == before
    return False


def depth(n: int) -> int:
    if n == 0:
        return 0
    return 1 + depth(n - 1)


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
print(lower(20), sys.getrecursionlimit())
for invalid in [0, -1]:
    try:
        sys.setrecursionlimit(invalid)
    except ValueError:
        print("invalid", sys.getrecursionlimit())
try:
    sys.setrecursionlimit(2147483648)
except OverflowError:
    print("overflow", sys.getrecursionlimit())
sys.setrecursionlimit(180)
print(sys.getrecursionlimit(), depth(100))
sys.setrecursionlimit(60)
try:
    print(depth(100))
except RecursionError:
    print("lowered caught")
print(depth(3))
sys.setrecursionlimit(original)
