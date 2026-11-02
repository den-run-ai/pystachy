# Finalizers called near the recursion limit must run with the unwound depth.
# The recursive call remains finite (100) even before guard enforcement (#988).
import sys

entered = [0]
exited = [0]


class Guard:
    def __enter__(self) -> "Guard":
        entered[0] += 1
        return self

    def __exit__(self, kind, error, traceback) -> bool:
        exited[0] += 1
        return False


def nested(n: int) -> int:
    with Guard():
        if n == 0:
            return 7
        return nested(n - 1)


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for attempt in range(4):
    entered[0] = 0
    exited[0] = 0
    try:
        print(nested(100))
    except RecursionError:
        print("caught", entered[0] > 0, entered[0] == exited[0])
    print(nested(3), entered[0] == exited[0])
sys.setrecursionlimit(original)
