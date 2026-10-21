# dataclasses.replace constructs a new object; direct reinitialization does not.
from dataclasses import dataclass, replace


@dataclass(init=False)
class Record:
    value: int

    def __init__(self, value: int) -> str | None:
        self.value = value
        print("record init", value)
        return "" if value else None


r = Record(0)
print(replace(r).value)
try:
    replace(r, value=1)
except TypeError as e:
    print("TypeError", e)
print("direct", repr(r.__init__(2)), r.value)
