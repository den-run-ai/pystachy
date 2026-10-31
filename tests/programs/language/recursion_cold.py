# A delayed publication must preserve the entry check and the failing child's
# side-effect order. Calibrate one spare frame without assuming Python/native
# count the module and interpreter adapters identically.
import sys

seen: list[int] = [0, 0]


def callback() -> None:
    seen[1] += 1


def cold(n: int) -> int:
    seen[0] += 1
    if n < 0:
        callback()
        raise ValueError("cold callback completed")
    return n + 1


def one_spare(n: int) -> int:
    if n == 0:
        return -3
    try:
        result = one_spare(n - 1)
    except RecursionError:
        return 0
    if result == 0:
        before_body = seen[0]
        before_callback = seen[1]
        try:
            cold(-1)
        except RecursionError:
            # cold itself enters, then callback's entry fails. An eager depth
            # test would skip the first write; missing publication runs callback.
            if seen[0] == before_body + 1 and seen[1] == before_callback:
                return 1
            return -1
        return -2
    return result


def change_limit() -> None:
    sys.setrecursionlimit(3)


def cold_limit(n: int) -> int:
    seen[0] += 1
    if n < 0:
        change_limit()
        raise ValueError("unexpected limit change")
    return n


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for repeat in range(3):
    print("one spare", one_spare(100) == 1)
    print("normal", cold(4))
    before_body = seen[0]
    before_callback = seen[1]
    try:
        cold(-1)
    except ValueError:
        print("error", seen[0] - before_body, seen[1] - before_callback)
    try:
        cold_limit(-1)
    except RecursionError:
        print("limit preserved", sys.getrecursionlimit() == 60)
sys.setrecursionlimit(original)
