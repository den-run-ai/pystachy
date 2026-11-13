# from __future__ import annotations: an annotation is never evaluated, so Literal may be a name
# that only an if TYPE_CHECKING: block imports. Its strings are values there too.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


class Door:
    state: Literal["open", "closed"] = "closed"

    def __init__(self, level: Literal[1, 2] = 1) -> None:
        self.level: Literal[1, 2] = level

    def swing(self) -> Literal["open", "closed"]:
        self.state = "open" if self.state == "closed" else "closed"
        return self.state


def name(x: Literal["hello"]) -> str:
    return x


def never(flag: bool) -> Literal[False]:
    return False


def nested(x: Literal[Literal["a"], "b"], n: Literal[Literal[1], 2] = 1) -> str:
    return x * n


def maybe(flag: bool) -> Literal["yes", None]:
    return "yes" if flag else None


def raw(x: Literal[b"r"]) -> int:
    return len(x)


d = Door(2)
print(d.level, d.swing(), d.swing())
print(name("hello"), never(True))
print(nested("a"), nested("b", 2))
print(maybe(True), maybe(False), raw(b"r"))
