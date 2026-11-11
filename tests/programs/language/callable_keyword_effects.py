from typing import Callable

events: list[str] = []


def arg(label: str, value: int) -> int:
    events.append(label)
    return value


def function(x: int, /, y: int = 4) -> int:
    events.append("body")
    return x + y


def callee() -> Callable[[int, int], int]:
    events.append("callee")
    return function


print(callee()(arg("pos", 3), y=arg("kw", 5)), events)
events.clear()


def failures(fn: Callable[[int, int], int]) -> None:
    try:
        fn(x=arg("posonly", 1), y=arg("later", 2))
    except TypeError as error:
        print(str(error), events)
    events.clear()
    try:
        fn(arg("arg1", 1), arg("arg2", 2), y=arg("duplicate", 3))
    except TypeError as error:
        print(str(error), events)
    events.clear()
    try:
        fn(arg("arg", 1), missing=arg("unknown", 9))
    except TypeError as error:
        print(str(error), events)
    events.clear()


failures(function)


def optional(fn: Callable[[int, int], int] | None) -> None:
    try:
        fn(arg("before-none", 1), y=arg("also-before-none", 2))
    except TypeError as error:
        print(str(error), events)


optional(None)


class Holder:
    def __init__(self, value: int) -> None:
        self.value = value

    def read(self, x: int, y: int = 0) -> int:
        return self.value + x + y


holders = [Holder(10)]


def replace() -> int:
    holders[0] = Holder(20)
    return 2


held: Callable[[int, int], int] = holders[0].read
print(held(1, y=replace()), holders[0].value)
