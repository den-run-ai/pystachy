# pystachy: dynamic-any
from typing import Any


class C(Exception):
    def one(self, first: Any) -> None:
        super().__init__(first)
        print("one done")

    def two(self, first: Any, second: Any) -> None:
        super().__init__(first, second)
        print("two done")

    def invalid(self, first: Any) -> None:
        super().__init__(first)


value: C | None = None
C.one(value, int)
C.two(value, str, None)
try:
    C.invalid(value, "invalid")
except TypeError as error:
    print(str(error))
