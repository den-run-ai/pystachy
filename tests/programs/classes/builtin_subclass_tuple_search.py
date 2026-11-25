# A tuple search (in, count(), index()) for an object of a class deriving from list or dict, or
# in a tuple that holds one, beside an object of a class whose __eq__ takes only the container
# (its parameter is annotated list[int] | None or dict[str, int] | None). CPython calls the
# method, with the object; the method takes the container here, as == hands it over (#1763).
# Where the method takes the object (unannotated, object), it gets the object itself. Beside a
# list or dict, such an object is compared as its container, whose == it inherits
class Stack(list[int]):
    pass


class Table(dict[str, int]):
    pass


class Typed:
    def __eq__(self, other: list[int] | None) -> bool:
        print("Typed.__eq__", other)
        return other is not None and len(other) == 1


class TypedD:
    def __eq__(self, other: dict[str, int] | None) -> bool:
        print("TypedD.__eq__", other)
        return True


class Loose:
    def __eq__(self, other) -> bool:
        print("Loose.__eq__", type(other).__name__)
        return True


class Obj:
    def __eq__(self, other: object) -> bool:
        print("Obj.__eq__", type(other).__name__)
        return isinstance(other, Stack)


s = Stack()
s.append(1)
t = Table()
t["a"] = 1
print(s in (Typed(), 5))
print(s in (5, Typed()), s not in (Typed(),))
print((Typed(), 5, Typed()).count(s), (5, Typed()).index(s))
print(Typed() in (s, 5), (s, s).count(Typed()))
print(t in (TypedD(), 5), TypedD() in (t,))
print(s in (Loose(), 5), s in (Obj(),))
print(Typed() == s, s == Typed())
two = Stack()
two.append(1)
two.append(2)
print(two in (Typed(),), (Typed(), Typed()).count(two))
print([1] in (s, 5), s in ([1],), (s, [1], [2]).count([1]), ([2], s).index([1]))
print({"a": 1} in (t,), t in (5, {"a": 1}), s in (two,), two in (s, two))
