# error: typing.Any is only supported in
from typing import Any


class Stack(list[Any]):
    pass


s = Stack()
