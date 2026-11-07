# pystachy: dynamic-any
# Class records cannot represent computed or mutable class metadata yet.
from typing import Any


class Fixed:
    pass


class Computed:
    __module__ = "wi" + "re"


values: list[Any] = [Fixed(), Computed(), 3]
for value in values:
    try:
        cls = type(value)
        print(cls.__name__)
    except NotImplementedError:
        print("class metadata unavailable")
