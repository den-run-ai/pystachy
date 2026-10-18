# error: __next__() returns both int and str (each function has one return type)
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


print(next(Mixed(True)))
