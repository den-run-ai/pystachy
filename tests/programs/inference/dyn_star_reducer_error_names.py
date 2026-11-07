# pystachy: dynamic-any
# Named methods and callable fields retain their selected function's qualified name.
from typing import Any


def plain(value: int = 0) -> int:
    return value


class Holder:
    def __init__(self) -> None:
        self.function: Any = plain

    def method(self, value: int = 0) -> int:
        return value


holder: Any = Holder()
bound: Any = holder.method
bad: Any = 3
first: Any = {"value": 1}
second: Any = {"value": 2}
for case in range(5):
    try:
        if case == 0:
            holder.method(*bad)
        elif case == 1:
            holder.function(*bad)
        elif case == 2:
            bound(*bad)
        elif case == 3:
            holder.method(**first, **second)
        else:
            holder.function(**first, **second)
    except TypeError as error:
        print(str(error))
