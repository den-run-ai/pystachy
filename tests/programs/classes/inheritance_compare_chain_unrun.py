# A hierarchy that defines only __lt__ (enough for sorted()) and a chained comparison whose <= no
# class of it can compare. CPython raises TypeError only where such a chain runs: this program
# never runs it, and prints the sorted keys. (#908: the chain's join took an edge from the block
# the raising link ends, and the program did not compile.)
import sys


class B:
    def __init__(self, k: int) -> None:
        self.k = k

    def __lt__(self, other: "B") -> bool:
        return self.k < other.k


class S(B):
    pass


def between(lo: B, x: B, hi: B) -> bool:
    return lo <= x < hi


items: list[B] = [S(3), B(1), S(2)]
print([x.k for x in sorted(items)])
if "--between" in sys.argv:
    print(between(items[0], items[1], items[2]))
