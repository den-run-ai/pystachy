# error: lib_functools_ordering_name.py:10: error: name '_A__pys_ordering' is not defined
class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "A") -> bool:
        return self.n < other.n

    def __ge__(self, other: "A") -> bool:
        return not __pys_ordering(self, other, "__lt__")


print(A(1) >= A(2))
