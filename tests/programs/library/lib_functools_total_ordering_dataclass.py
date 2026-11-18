# functools.total_ordering above and below @dataclass, whose __eq__ the class keeps.
from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass
class Above:
    x: int
    label: str = ""

    def __lt__(self, other):
        if not isinstance(other, Above):
            return NotImplemented
        return self.x < other.x


@dataclass(frozen=True)
@total_ordering
class Below:
    x: int

    def __gt__(self, other: "Below") -> bool:
        return self.x > other.x


a = [Above(2, "b"), Above(1, "a"), Above(2, "c")]
print(a[0] > a[1], a[0] >= a[2], a[0] <= a[2], a[0] == a[2], a[0] == Above(2, "b"), sorted(a)[0].label)
b = [Below(3), Below(1)]
print(b[0] < b[1], b[0] <= b[0], b[1] <= b[0], b[0] >= b[1], min(b).x, b[0] == Below(3))
for other in [3]:
    try:
        print(a[0] >= other)
    except TypeError as e:
        print("TypeError", e)
