# error: 'object' object has no method
# crossing matrix (tools/crossing_matrix.py), column protocol_to_object, row template: without `isinstance()` narrowing
from typing import Protocol


class T:
    def __init__(self, item):
        self.item = item

    def describe(self) -> str:
        return "T" + repr(self.item)

    def __repr__(self) -> str:
        return "T(" + repr(self.item) + ")"


class Described(Protocol):
    def describe(self) -> str: ...


def main() -> None:
    x: Described = T('s')
    y: object = x
    if isinstance(y, T):
        print(y.describe())
    else:
        print('not narrowed')


main()
