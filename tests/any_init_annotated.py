from typing import Annotated, Any


class Holder:
    def __init__(self, value: Annotated[Any, "metadata"]) -> None:
        self.value = value


print(Holder(1).value, Holder("text").value)
