# Literal[...] as an annotation is the type of its values: CPython does not check a value
# against it. Its strings are values, not forward references.
import typing
from typing import Literal, Optional

import typing_extensions

Mode = Literal["r", "w"]


class Session:
    state: Literal["open", "closed"] = "open"

    def __init__(self, level: Literal[1, 2, 3] = 1) -> None:
        self.level: Literal[1, 2, 3] = level
        self.quiet: Literal[True, False] = False

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> Literal[False]:
        self.state = "closed"
        return False


def never() -> Literal[False]:
    return False


def pick(x: Literal[1, 2], mode: Literal["r", "w"] = "r") -> Literal["a", "b"]:
    return "a" if x == 1 and mode == "r" else "b"


def aliased(mode: Mode) -> str:
    return mode.upper()


def sign(x: int) -> Literal[-1, 0, 1]:
    return -1 if x < 0 else 1 if x > 0 else 0


def maybe(flag: bool) -> Literal["yes", None]:
    return "yes" if flag else None


def optional(flag: bool) -> Optional[Literal[b"raw"]]:
    return b"raw" if flag else None


def mixed(x: Literal[0, "zero"]) -> str:
    if isinstance(x, int):
        return "int " + str(x)
    return "str " + x


def nested(x: Literal[Literal[1, 2], Literal[3]]) -> int:
    return x * 2


def qualified(x: typing.Literal["q"], y: typing_extensions.Literal[5]) -> str:
    return x * y


def quoted(x: "Literal['s']") -> str:
    return x + x


def unchecked(x: Literal["only"]) -> str:
    return x


print(never(), pick(1), pick(2), pick(1, "w"), aliased("w"))
print(sign(-5), sign(0), sign(7), maybe(True), maybe(False), optional(True), optional(False))
print(mixed(0), mixed("zero"), nested(3), qualified("q", 5), quoted("s"), unchecked("other"))
with Session(2) as s:
    print(s.state, s.level, s.quiet)
print(s.state)
