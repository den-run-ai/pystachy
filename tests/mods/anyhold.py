from __future__ import annotations
from typing import Any
import typing


def ident(x: Any) -> Any:
    return x


class Holder:
    def __init__(self, value: typing.Any) -> None:
        self.value = value


class ObjectHolder:
    def __init__(self, value: object) -> None:
        self.value = value
