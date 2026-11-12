from dataclasses import dataclass


@dataclass
class Point:
    value: int


@dataclass
class Container:
    point: Point | None


def present(value: Point | None) -> bool:
    match value:
        case Point():
            return True
    return False


def nested(value: Container) -> int:
    match value:
        case Container(Point(number)):
            return number
    return -1


print(present(None), present(Point(3)))
print(nested(Container(None)), nested(Container(Point(3))))
