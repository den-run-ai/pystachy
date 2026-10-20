# error: typing.Any is only supported
from typing import Any


class Item:
    value: Any = 1


print(Item().value)
