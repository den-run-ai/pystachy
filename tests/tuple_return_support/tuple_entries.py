from __future__ import annotations

from typing import Annotated, Any


class State:
    def __init__(self, name: str):
        self.name = name


def default(flag: bool, tag: Any) -> Annotated[tuple[State | None, Any], "entry"]:
    if flag:
        return None, "ok"
    return State("fresh"), tag


DEFAULT_ENTRY = (None, "ok")
