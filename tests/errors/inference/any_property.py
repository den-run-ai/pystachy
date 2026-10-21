# error: any_property.py:11: error: typing.Any is only supported in the parameter and return annotations of a function
# A property needs a return annotation that gives its type, which Any does not
from typing import Any


class C:
    def __init__(self) -> None:
        self.v = 1

    @property
    def value(self) -> Any:
        return self.v


print(C().value)
