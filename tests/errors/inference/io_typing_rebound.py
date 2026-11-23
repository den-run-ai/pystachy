# error: cannot infer the type of field 'value'
from typing import IO


class Contents:
    def __init__(self, source: IO[str]) -> None:
        source = open("/dev/null", "rb")
        self.value = source.read()


with open("/dev/null") as f:
    print(Contents(f).value)
