# Zero-argument super() is anchored to the class defining the method, even when the receiver is
# two levels below it. Explicit super(C, self) skips C and preserves the same concrete receiver.
class Root:
    def __init__(self, n: int) -> None:
        self.n = n

    def mark(self) -> str:
        return "R"

    def trace(self, suffix: str = "!") -> str:
        return self.mark() + str(self.n) + suffix


class Middle(Root):
    def __init__(self, n: int) -> None:
        super().__init__(n + 1)
        self.m = n + 2

    def mark(self) -> str:
        return "M"

    def trace(self, suffix: str = "?") -> str:
        return "M(" + super().trace(suffix) + ")"

    def root_trace(self) -> str:
        return super(Middle, self).trace(".")


class Leaf(Middle):
    def __init__(self, n: int) -> None:
        super(Leaf, self).__init__(n + 10)
        self.end = n + 20

    def mark(self) -> str:
        return "L"

    def trace(self, suffix: str = ":") -> str:
        return "L(" + super().trace(suffix) + ")"

    def middle_trace(self) -> str:
        return super(Leaf, self).trace(";")

    def root_direct(self) -> str:
        return super(Middle, self).trace("/")


class Inherited(Leaf):
    pass


print(Root(1).trace(), Middle(2).trace())
for x in [Leaf(3), Inherited(4)]:
    print(x.n, x.m, x.end)
    print(x.trace(), x.middle_trace(), x.root_trace(), x.root_direct())
    print(Root.trace(x), Middle.trace(x), Leaf.trace(x))
