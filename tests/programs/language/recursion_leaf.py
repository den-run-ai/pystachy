# A leaf still fails entry at the limit; omitting only its invisible depth writes
# must not run the body. Recover in the deepest active frame, then try a leaf.
import sys

seen: list[int] = [0]


def leaf() -> int:
    seen[0] += 1
    return seen[0]


def deepest() -> int:
    try:
        return deepest()
    except RecursionError:
        before = seen[0]
        try:
            leaf()
        except RecursionError:
            return seen[0] - before
        return -1


def divide(n: int) -> int:
    try:
        return 12 // n
    finally:
        seen[0] += 1


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for repeat in range(3):
    print("entry", deepest())
    print("recovered", leaf() > 0)
    before = seen[0]
    try:
        divide(0)
    except ZeroDivisionError:
        print("cleanup", seen[0] - before)
    print("return", divide(3))
sys.setrecursionlimit(original)
