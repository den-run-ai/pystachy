# typing.Literal[...] annotations have the type of their values: CPython checks none of them.
import typing
import typing as t
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

Mode = Literal["standard", "salvage"]
Level = Literal[0, 1, -1]
Nested = Literal[Literal["a", "b"], "c"]


class Color(Enum):
    RED = 1
    BLUE = 2


@dataclass
class Job:
    mode: Mode = "standard"
    level: Literal[0, 1] = 0
    done: Literal[False] = False


def normalize(mode: Mode = "standard") -> Literal["standard", "salvage"]:
    if mode == "salvage":
        return "salvage"
    return "standard"


def flag(n: int) -> Literal[False]:
    # (no annotation is checked: True is returned as CPython returns it)
    return n > 3


def qualified(x: typing.Literal["q"], y: t.Literal[b"y"]) -> "Literal['q', 'r']":
    return x


def switched(v: "Literal['on', 'off']") -> Optional[Literal["on"]]:
    return "on" if v == "on" else None


def none_or_text(n: int) -> Literal["x", None]:
    return "x" if n > 0 else None


def mixed(n: int) -> Literal["text", 7]:
    if n == 0:
        return "text"
    return 7


def color(c: Literal[Color.RED, Color.BLUE]) -> Literal[Color.RED]:
    return Color.RED if c is Color.BLUE else c


def level(n: Level) -> Level:
    return -n


def nested(v: Nested) -> Nested:
    return v


class Entry:
    def __enter__(self) -> None:
        print("enter")

    def __exit__(self, a: type[BaseException] | None, b: BaseException | None, c: object) -> Literal[False]:
        print("exit")
        return False


job = Job()
state: Literal["idle", "busy"] = "idle"
print(normalize(), normalize("salvage"), flag(1), flag(9), qualified("q", b"y"))
print(switched("on"), switched("off"), none_or_text(1), none_or_text(0), mixed(0), mixed(1))
print(color(Color.BLUE), color(Color.RED), level(1), level(-1), nested("c"), job, state)
with Entry():
    print("body")
