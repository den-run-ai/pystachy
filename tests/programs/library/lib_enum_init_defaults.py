# An enum __init__ whose parameters have defaults: a member's value leaves them out, by
# position and by keyword, also where the def statement follows the members.
from enum import Enum


class Mixed(Enum):
    A = (1, "one")
    B = (2, "two")
    ALIAS = (1, "one")

    def __init__(self, n, name, /, half=0.5, *, flag=True, tag="t", count=-3) -> None:
        self.n = n
        self.title = name
        self.half = half
        self.flag = flag
        self.tag = tag
        self.count = count


for m in Mixed:
    print(m.name, m.n, m.title, m.half, m.flag, m.tag, m.count)
print(Mixed.ALIAS is Mixed.A)
