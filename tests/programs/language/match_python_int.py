# pystachy: python-int
from dataclasses import dataclass


def scalar(value: int) -> str:
    match value:
        case [first, second]:
            return "sequence"
        case -9223372036854775808:
            return "minimum"
        case 9223372036854775808:
            return "large"
        case captured:
            return str(captured)


print(scalar(1), scalar(-9223372036854775808), scalar(9223372036854775808))


def pair(value: tuple[int, int]) -> int:
    match value:
        case (0, number) | (number, 0) if number > 9223372036854775807:
            return number
        case _:
            return -1


print(pair((0, 9223372036854775808)), pair((9223372036854775809, 0)), pair((0, 1)))


@dataclass
class Box:
    value: int


def unbox(value: Box) -> int:
    match value:
        case Box(number):
            return number
    return -1


print(unbox(Box(18446744073709551616)))
