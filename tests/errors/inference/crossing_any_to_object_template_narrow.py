# error: 'object' object has no method
# crossing matrix (tools/crossing_matrix.py), column any_to_object, row template: without `isinstance()` narrowing
# pystachy: dynamic-any
from typing import Any


class T:
    def __init__(self, item):
        self.item = item

    def describe(self) -> str:
        return "T" + repr(self.item)

    def __repr__(self) -> str:
        return "T(" + repr(self.item) + ")"


def main() -> None:
    x: Any = T('s')
    y: object = x
    if isinstance(y, T):
        print(y.describe())
    else:
        print('not narrowed')


main()
