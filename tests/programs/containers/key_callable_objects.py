# Objects whose class defines __call__ as key functions: sorted(), min(), max(), list.sort()
# and the library's key= parameters call them once per item, in CPython's order
import bisect
import heapq


class ByIndex:
    def __init__(self, i: int) -> None:
        self.i = i
        self.calls = 0

    def __call__(self, row: list[int]) -> int:
        self.calls += 1
        return row[self.i]


class Neg:
    def __call__(self, x: int) -> int:
        print("key", x)
        return -x


rows = [[3, 1], [1, 2], [2, 0]]
k = ByIndex(1)
print(sorted(rows, key=k), min(rows, key=k), max(rows, key=ByIndex(0)), k.calls)
rows.sort(key=ByIndex(0), reverse=True)
print(rows, min([5, 7], [6, 1], key=k), max(3, 9, 4, key=Neg()))
print(sorted([2, 3, 1], key=Neg()), list(map(Neg(), [4])))
print(heapq.nsmallest(2, [5, 1, 4], key=Neg()), bisect.bisect([-9, -5, -1], 3, key=Neg()))
