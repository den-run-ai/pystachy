from typing import Iterable


class Names:
    def __init__(self, groups: Iterable[list[str]]) -> None:
        self.seen: dict[str, int] = {}
        for group in groups:
            self.seen[group[0]] = len(group)

    def size(self) -> int:
        return len(self.seen)


class Visitor:
    def visit(self) -> int:
        return 0


class Emitter(Visitor):
    def __init__(self, names: Names) -> None:
        self.names = names

    def visit(self) -> int:
        return self.names.size()


def emit(visitor: Visitor) -> int:
    return visitor.visit()


def groups():
    yield ["g", "h"]
    yield ["i"]


one: Names = Names([["a", "b"]])
two: Names = Names((["c"], ["d", "e"]))
three: Names = Names(groups())
objects: list[Names] = [one, two, three]
print([n.size() for n in objects])
print(one.seen, two.seen, three.seen)
print(emit(Emitter(one)), emit(Emitter(three)))
print(type(one) is Names, type(two) is Names, isinstance(three, Names))


class Total:
    total: int

    def __init__(self, values: Iterable[int]) -> None:
        self.total = sum(values)

    def value(self) -> int:
        return self.total


class Doubled(Total):
    def value(self) -> int:
        return self.total * 2


class Offset(Total):
    def __init__(self, values: Iterable[int], offset: int) -> None:
        super().__init__(values)
        self.offset: int = offset

    def value(self) -> int:
        return self.total + self.offset


def value(total: Total) -> int:
    return total.value()


print(value(Total([1, 2])), value(Doubled((3, 4))))
print(value(Offset([5, 6], 7)), value(Offset((8, 9), 10)))
