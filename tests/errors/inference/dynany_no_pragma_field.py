# error: typing.Any is only supported in the parameter and return annotations of a function
# Without the "# pystachy: dynamic-any" comment, Any keeps its inference-only meaning: a field
# that holds any value is unsupported, as before.
from typing import Any


class Box:
    def __init__(self) -> None:
        self.value: Any = None


print(Box().value)
