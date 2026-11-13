# A union's nested class descriptors must dispatch to the class owning the storage.
# C holds a pointer; D holds two integers, so selecting the wrong repr misreads fields.
class C:
    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return f"C({self.label})"


class D:
    def __init__(self, count: int) -> None:
        self.count = count
        self.extra = count + 10

    def __repr__(self) -> str:
        return f"D({self.count}:{self.extra})"


def mapping(x: dict[str, list[C]] | dict[str, list[D]] | int) -> None:
    print(repr(x), [x], (x, 7), {"x": x})


def nested(x: list[int | list[C]] | list[D] | str) -> None:
    print(repr(x), [x], (x, 8), {"x": x})


mapping({"c": [C("left")]})
mapping({"d": [D(7)]})
mapping(2)
values: list[int | list[C]] = [1, [C("nested")]]
nested(values)
nested([D(11)])
nested("s")
