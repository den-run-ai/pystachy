# error: cannot infer the type of field 'value'; annotate it (self.value: T = ...)
# A global that the branches of an if statement bind to values of different types gives a field
# stored from it no type: its annotation gives one.
import sys

if sys.maxsize > 1:
    LIMIT = 10
else:
    LIMIT = "none"


class Box:
    def __init__(self) -> None:
        self.value = LIMIT


print(Box().value)
