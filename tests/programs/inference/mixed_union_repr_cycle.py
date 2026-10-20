"""A native object may link back to a container held inside a union box."""
from __future__ import annotations


class Link:
    def __init__(self) -> None:
        self.value: int | list[Link] | dict[str, Link] = 0
        self.fail = False

    def __repr__(self) -> str:
        if self.fail:
            raise ValueError("repr failed")
        return "Link(" + repr(self.value) + ")"


def show(value: int | list[Link] | dict[str, Link]) -> None:
    print(str(value), repr(value), f"{value}")


link = Link()
items = [link]
link.value = items
show(items)
mapping = {"back": link}
link.value = mapping
show(mapping)
show(items)
link.fail = True
try:
    show(mapping)
except ValueError as error:
    print(str(error))
link.fail = False
show(mapping)
