# __next__() annotated Any returning an int or a str: int | str.
from typing import Any


class Mixed:
    def __init__(self, flag: bool) -> None:
        self.flag = flag

    def __iter__(self) -> Any:
        return self

    def __next__(self) -> Any:
        if self.flag:
            return 1
        return "x"


print(repr(next(Mixed(True))), repr(next(Mixed(False))))
