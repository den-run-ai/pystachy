# Source-defined descriptors and methods need no dynamic Any opt-in.
from typing import Callable


class Error(Exception):
    @property
    def args(self) -> tuple[str, str]:
        return ("custom", "args")


class Child(Error):
    pass


class Done(StopIteration):
    def value(self) -> int:
        return 42


print(Error(1).args, Child(2).args)
try:
    raise Child(3)
except Child as error:
    print(error.args)
value: Callable[[], int] = Done(4).value
print(value())
