# error: Point() accepts 1 positional sub-patterns (2 given)
from dataclasses import dataclass, field


@dataclass
class Point:
    x: int
    y: int = field(kw_only=True)


match Point(1, y=2):
    case Point(x, y):
        print(x, y)
