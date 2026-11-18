# The temporary unbound super initializer cannot validate a runtime-selected ordinary
# class or dynamic replacement receiver. It raises NotImplementedError only in that
# arm, after evaluating arguments. CPython accepts both pairs below.
# pystachy: dynamic-any
from typing import Any


def receiver() -> int:
    print("receiver argument")
    return 7


class C(Exception):
    def first(self, kind: Any) -> None:
        super().__init__(kind, receiver())
        print("first done")

    def second(self, kind: Any, replacement: Any) -> None:
        super().__init__(kind, replacement)
        print("second done")


value: C | None = None
try:
    C.first(value, int)
except NotImplementedError as error:
    print(str(error))
try:
    C.second(value, int, receiver())
except NotImplementedError as error:
    print(str(error))
