"""Snapshot a callback once, including when it mutates the source or raises mid-search."""
from typing import Callable


def project(n: int) -> int:
    seen.append(n)
    callbacks[0] = alternate
    return n + 1


def alternate(n: int) -> int:
    seen.append(-n)
    return n + 10


def make_key(offset: int) -> Callable[[int], int]:
    state = [offset]

    def key(n: int) -> int:
        state[0] += n
        return state[0]
    return key


class Receiver:
    def __init__(self, offset: int):
        self.offset = offset

    def key(self, n: int) -> int:
        self.offset += n
        seen.append(self.offset)
        if n == 2:
            raise ValueError("stop")
        return self.offset


def search(key) -> int:
    result = 0
    for item in [1, 2, 3]:
        result += key(item)
    return result


def call_search(key: Callable[[int], int]) -> int:
    return search(key)


seen: list[int] = []
callbacks: list[Callable[[int], int]] = [project]
print(call_search(callbacks[0]), call_search(callbacks[0]), seen)
first = make_key(5)
second = make_key(19)
print(call_search(first), call_search(second), call_search(first))
r1 = Receiver(50)
r2 = Receiver(70)
keys: list[Callable[[int], int]] = [r1.key, r2.key, r1.key]
for key in keys:
    try:
        call_search(key)
    except ValueError as err:
        print(str(err), r1.offset, r2.offset, seen)
