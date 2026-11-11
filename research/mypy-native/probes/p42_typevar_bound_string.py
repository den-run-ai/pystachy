from typing import TypeVar
class Type:
    def __init__(self, line: int) -> None:
        self.line = line
class Instance(Type):
    pass
T = TypeVar("T", bound="Type")
def set_line(t: T, line: int) -> T:
    t.line = line
    return t
i = set_line(Instance(1), 7)
print(type(i).__name__, i.line)
