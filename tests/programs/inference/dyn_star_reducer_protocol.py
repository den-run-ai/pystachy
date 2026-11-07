# pystachy: dynamic-any
# Star expansion alone registers iterator and length-hint hooks, without list().
from typing import Any

EVENTS: list[str] = []


class Iter:
    def __init__(self) -> None:
        self.index = 0

    def __iter__(self) -> "Iter":
        EVENTS.append("iterator iter")
        return self

    def __next__(self) -> int:
        EVENTS.append("next:" + str(self.index))
        if self.index == 2:
            raise StopIteration
        self.index += 1
        return self.index

    def __length_hint__(self) -> int:
        EVENTS.append("iterator hint")
        return 9


class Source:
    def __init__(self, mode: int) -> None:
        self.mode = mode

    def __iter__(self) -> Iter:
        EVENTS.append("iter")
        return Iter()

    def __len__(self) -> int:
        EVENTS.append("len")
        if self.mode == 1:
            return -1
        if self.mode >= 2:
            raise TypeError("no length")
        return 2

    def __length_hint__(self) -> int:
        EVENTS.append("hint")
        if self.mode == 2:
            return 2
        if self.mode == 3:
            raise TypeError("no hint")
        return -1


class Index:
    def __index__(self) -> int:
        EVENTS.append("index must not run")
        return 1


class HintValues:
    def __init__(self, mode: int) -> None:
        self.mode = mode

    def __iter__(self) -> Iter:
        EVENTS.append("hint iter")
        return Iter()

    def __length_hint__(self) -> Any:
        EVENTS.append("hint value")
        if self.mode == 0:
            return "wrong"
        if self.mode == 1:
            return None
        if self.mode == 2:
            return Index()
        if self.mode == 3:
            return True
        raise ValueError("hint failed")


def target(a: int, b: int, c: int = 0) -> int:
    EVENTS.append("call")
    return a + b + c


def note(label: str, value: Any) -> Any:
    EVENTS.append(label)
    return value


function: Any = target
for mode in range(5):
    EVENTS.clear()
    try:
        print("sole", mode, function(*note("arg", Source(mode)), c=note("kw", 3)))
    except (TypeError, ValueError) as error:
        print("sole error", mode, type(error).__name__, str(error))
    print(EVENTS)
EVENTS.clear()
print("multiple", function(*note("arg", Source(0)), *note("empty", []), c=note("kw", 4)))
print(EVENTS)
EVENTS.clear()
print("iterator", function(*note("arg", Iter()), c=note("kw", 5)))
print(EVENTS)
for mode in range(5):
    EVENTS.clear()
    try:
        print("hint", mode, function(*note("arg", HintValues(mode)), c=note("kw", 6)))
    except (TypeError, ValueError) as error:
        print("hint error", mode, type(error).__name__, str(error))
    print(EVENTS)
