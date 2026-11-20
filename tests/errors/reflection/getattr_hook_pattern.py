# error: getattr_hook_pattern.py:17: error: class patterns require a dataclass without a hierarchy, attribute hooks or custom __match_args__
# A class pattern reads the object's attributes with getattr(), which reaches __getattr__ in
# CPython (#1536): patterns of a class that defines one stay an error.
from dataclasses import dataclass


@dataclass
class Point:
    x: int

    def __getattr__(self, name: str) -> int:
        return 0


def first(p: Point) -> int:
    match p:
        case Point(x=1):
            return 1
    return 0


print(first(Point(1)))
