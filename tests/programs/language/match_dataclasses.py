from dataclasses import dataclass, field


@dataclass
class Point:
    x: int
    y: int
    label: str = field(default="point", kw_only=True)


def describe(point: Point) -> str:
    match point:
        case Point(0, y):
            return "axis:" + str(y)
        case Point(x=x, y=y, label=name):
            return name + ":" + str(x + y)
    return "none"


print(describe(Point(0, 7)), describe(Point(2, 3, label="sum")))


@dataclass(match_args=False)
class Named:
    value: int


def named(value: Named) -> int:
    match value:
        case Named(value=number):
            return number
    return -1


print(named(Named(4)))


class Mutate:
    def __init__(self, owners: "list[Container]") -> None:
        self.owners = owners

    def __eq__(self, other: int) -> bool:
        self.owners[0].second = [99]
        return other == 1


@dataclass
class Container:
    first: Mutate
    second: list[int]


def aliased(value: Container) -> int:
    match value:
        case Container(1, held):
            return held[0]
    return -1


owners: list[Container] = []
value = Container(Mutate(owners), [3])
owners.append(value)
print(aliased(value), value.second)


def other(value: int) -> int:
    match value:
        case Point(x, y):
            return x + y
        case _:
            return value


print(other(9))
