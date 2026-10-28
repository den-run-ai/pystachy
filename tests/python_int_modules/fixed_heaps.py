# A module that does not opt in: heapq and bisect keep the ints past 64 bits of the lists it gives
# them, as they keep those of a module that opts in.
import bisect
import heapq


def push_range(h: list[int], n: int) -> None:
    for i in range(n):
        heapq.heappush(h, i)


def pop_two(h: list[int]):
    return (heapq.heappop(h), heapq.heappop(h))


def where(a: list[int], x: int) -> int:
    return bisect.bisect_left(a, x)
