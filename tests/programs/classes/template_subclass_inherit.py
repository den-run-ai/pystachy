# A subclass of a class template without an __init__ of its own: its objects run the
# template's, whose arguments type the fields, and it adds methods that read them (#962).
from typing import Any


class Style:
    def __init__(self, fmt: str, defaults: Any = None) -> None:
        self.fmt = fmt
        self.defaults = defaults


class StrStyle(Style):
    def render(self) -> str:
        return self.fmt + ":" + str(self.defaults)


print(StrStyle("x").render())
print(StrStyle("y", {"k": 1}).render())
