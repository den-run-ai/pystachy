from dataclasses import dataclass
from typing import Callable


def failed_tuple(value: tuple[int, int]) -> int:
    saved = 99
    match value:
        case (saved, 0):
            pass
    return saved


def alternatives(value: tuple[int, int]) -> int:
    saved = 99
    match value:
        case (saved, 0) | (0, saved):
            pass
    return saved


def nested(value: tuple[tuple[int, int], int]) -> tuple[int, int]:
    saved = 99
    last = 77
    match value:
        case ((saved, 0) | (0, saved), 1 as last):
            pass
    return saved, last


def as_pattern(value: tuple[int, int]) -> tuple[int, tuple[int, int]]:
    saved = 99
    whole = (77, 88)
    match value:
        case (saved, 0) as whole:
            pass
    return saved, whole


print("tuple", failed_tuple((1, 2)), failed_tuple((1, 0)))
print("alternatives", alternatives((1, 2)), alternatives((0, 5)), alternatives((5, 0)))
print("nested", nested(((0, 5), 2)), nested(((0, 5), 1)))
print("as", as_pattern((1, 2)), as_pattern((1, 0)))


@dataclass
class Pair:
    first: int
    second: int


def failed_class(value: Pair) -> int:
    saved = 99
    match value:
        case Pair(first=saved, second=0):
            pass
    return saved


print("class", failed_class(Pair(1, 2)), failed_class(Pair(1, 0)))


class Observe:
    def __init__(self, read: Callable[[], int], seen: list[int]) -> None:
        self.read = read
        self.seen = seen

    def __eq__(self, other: int) -> bool:
        self.seen.append(self.read())
        return other == 1


def callback() -> None:
    saved = 99
    seen: list[int] = []
    read = lambda: saved
    value = (1, Observe(read, seen))
    match value:
        case (saved, 1):
            pass
    print("equality callback", seen, saved, read())


def guarded() -> None:
    saved = 99
    read = lambda: saved
    match (1, 2):
        case (saved, _) if read() < 0:
            pass
        case _:
            print("failed guard", saved, read())


def closed(value: tuple[int, int]) -> Callable[[], int]:
    saved = 99
    read = lambda: saved
    match value:
        case (saved, 0):
            pass
    return read


callback()
guarded()
print("closed", closed((1, 2))(), closed((1, 0))())


class Private:
    def choose(self, value: tuple[int, int]) -> int:
        __saved = 99
        match value:
            case (__saved, 0):
                pass
        return __saved


print("private", Private().choose((1, 2)), Private().choose((1, 0)))


def nonlocal_capture() -> None:
    saved = 99

    def choose(value: tuple[int, int]) -> None:
        nonlocal saved
        match value:
            case (saved, 0):
                pass

    choose((1, 2))
    print("nonlocal failure", saved)
    choose((1, 0))
    print("nonlocal success", saved)


nonlocal_capture()


@dataclass
class Payload:
    items: list[str]
    check: int


def alias(value: Payload) -> list[str]:
    saved = ["old"]
    match value:
        case Payload(saved, 0):
            pass
    return saved


payload = Payload(["new"], 1)
print("failed alias", alias(payload), payload.items)
payload.check = 0
held = alias(payload)
held.append("shared")
print("matched alias", held is payload.items, payload.items)
