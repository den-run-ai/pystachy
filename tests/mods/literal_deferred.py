from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


class Switch:
    def __init__(self, state: Literal["on", "off"] = "off") -> None:
        self.state: Literal["on", "off"] = state


def flip(s: Switch) -> Literal["on", "off"]:
    s.state = "on" if s.state == "off" else "off"
    return s.state


def level(x: Literal[Literal[1], 2]) -> int:
    return x + 1
