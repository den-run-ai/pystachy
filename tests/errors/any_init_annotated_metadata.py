# error: unsupported type annotation
from typing import Annotated, Any


class Holder:
    def __init__(self, value: Annotated[int, Any]) -> None:
        self.value = value


print(Holder("text").value)
