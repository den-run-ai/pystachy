# Native recursion guards (#988): bounded calls exceed a small configured limit;
# exact boundary depths differ between Python and native implementation frames.
import sys
from collections.abc import Callable


def direct(n: int) -> int:
    if n == 0:
        return 0
    return 1 + direct(n - 1)


def tail(n: int) -> int:
    if n == 0:
        return 7
    return tail(n - 1)


def even(n: int) -> bool:
    if n == 0:
        return True
    return odd(n - 1)


def odd(n: int) -> bool:
    if n == 0:
        return False
    return even(n - 1)


class Walker:
    def step(self, n: int) -> int:
        if n == 0:
            return 0
        return 1 + self.step(n - 1)


original = sys.getrecursionlimit()
try:
    print(direct(1500))
except RecursionError:
    print("default caught")
sys.setrecursionlimit(60)
print(sys.getrecursionlimit())
try:
    print(direct(100))
except RecursionError:
    print("direct caught")
finally:
    print("direct finally")
try:
    print(tail(100))
except RecursionError:
    print("tail caught")
try:
    print(even(100))
except RecursionError:
    print("mutual caught")
walker = Walker()
try:
    print(walker.step(100))
except RecursionError:
    print("method caught")
callbacks: list[Callable[[int], int]] = [direct, walker.step]
for callback in callbacks:
    try:
        print(callback(100))
    except RecursionError:
        print("callback caught")
print(direct(4), tail(4), even(4), odd(4), walker.step(4))
# Many completed calls must not accumulate depth.
total = 0
for i in range(200):
    total += direct(3)
print(total)
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original)
