# EnumType calls an enum class's __init__ as a method: what it returns is dropped (no constructor
# checks for None), a member's items go to the parameters that take them by position (extra ones
# to *args), and a parameter they do not reach, a keyword-only one too, has its default value,
# whose type it takes where it has no annotation
from enum import Enum, IntEnum


class Returns(Enum):
    A = 1
    B = 2

    def __init__(self, x):
        self.x = x
        return x


class Extra(Enum):
    A = (1, 2)
    B = (3, 4)

    def __init__(self, *args: int, label='item') -> None:
        self.total: int = sum(args)
        self.label = label


class Marked(Enum):
    A = (1, "x")
    B = (2, "y")

    def __init__(self, n, /, name, *, flag=True, tag='t', scale=1.5) -> None:
        self.n = n
        self.title = name
        self.flag = flag
        self.tag = tag
        self.scale = scale


class Padded(IntEnum):
    LOW = 1
    HIGH = 2

    def __init__(self, n, note='plain', weight=3):
        self.note = note + str(n)
        self.weight = weight * n


print(Returns.A.x, Returns.B.x, list(Returns))
print(Extra.A.total, Extra.B.total, Extra.B.label)
print(Marked.A.n, Marked.A.title, Marked.B.flag, Marked.B.tag, Marked.A.scale)
print(Padded.LOW.note, Padded.HIGH.weight, Padded.HIGH + 1)
