# error: method 'get' of class 'Section' mentions TypeVar '_D', which is not supported: a method is not a template
from typing import TypeVar

_D = TypeVar("_D")


class Section:
    def __init__(self, name: str) -> None:
        self.name = name

    def get(self, key: str, default: _D | None = None) -> str | _D | None:
        return default
