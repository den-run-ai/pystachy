# pystachy: dynamic-any
# Dynamic dispatch must not bypass the native recursion limit (#988).
import sys
from typing import Any


def recurse(n: int, callback: Any) -> int:
    if n == 0:
        return 0
    return 1 + callback(n - 1, callback)


class Walker:
    def step(self, n: int, receiver: Any) -> int:
        if n == 0:
            return 0
        return 1 + receiver.step(n - 1, receiver)

    def __call__(self, n: int, receiver: Any) -> int:
        if n == 0:
            return 0
        return 1 + receiver(n - 1, receiver)


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
callback: Any = recurse
receiver: Any = Walker()
for attempt in range(3):
    try:
        print(callback(100, callback))
    except RecursionError:
        print("dynamic function")
    try:
        print(receiver.step(100, receiver))
    except RecursionError:
        print("dynamic method")
    try:
        print(receiver(100, receiver))
    except RecursionError:
        print("dynamic callable")
    print(callback(3, callback), receiver.step(3, receiver), receiver(3, receiver))
sys.setrecursionlimit(original)
