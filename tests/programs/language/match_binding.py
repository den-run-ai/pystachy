from typing import Callable


def factory(value: int) -> Callable[[], int]:
    captured = 0
    match value:
        case captured if captured < 0:
            pass
        case _:
            pass
    return lambda: captured


print(factory(5)(), factory(-2)())


def maybe(value: int) -> int:
    match value:
        case 1 as captured:
            pass
    try:
        return captured
    except UnboundLocalError:
        return -1


print(maybe(1), maybe(2))


class Private:
    def choose(self, value: int) -> int:
        match value:
            case __value:
                return __value


print(Private().choose(6))


def looping(values: list[int]) -> int:
    total = 0
    for value in values:
        match value:
            case 0:
                continue
            case -1:
                break
            case number:
                total += number
    return total


print(looping([0, 2, 3, -1, 9]))
