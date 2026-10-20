# error: method '__init__' of class 'Section' mentions TypeVar '_D', which is not supported: __init__() is not a template
from typing import TypeVar

_D = TypeVar("_D")


class Section:
    def __init__(self, name: str, default: _D) -> None:
        self.name = name
        self.default = default

    def get(self, key: str, default: _D | None = None) -> str | _D | None:
        return default
