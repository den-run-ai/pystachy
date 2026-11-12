# Fields typed by another class's class attributes, read through the class or a subclass.
from enum import Enum


class Color(Enum):
    RED = 1
    GREEN = 2


class Branch:
    BOOL = 100
    IS_ERROR = 101
    LABEL = "branch"
    NAMES = ["bool", "is_error"]


class Jump(Branch):
    pass


class Failure(Exception):
    CODE = 7


class Op:
    def __init__(self, traceback: bool) -> None:
        self.kind = Branch.IS_ERROR if traceback else Branch.BOOL
        self.label = Jump.LABEL
        self.names = Jump.NAMES
        self.kinds = [Branch.BOOL, Branch.IS_ERROR]
        self.code = Failure.CODE
        self.color = Color.GREEN
        self.seen = {Color.RED}


a = Op(False)
b = Op(True)
a.names.append("extra")
a.kinds.append(0)
print(a.kind, b.kind, a.label, b.names, Branch.NAMES, a.names is Branch.NAMES, a.kinds, b.kinds, a.code)
print(a.color, a.color.name, a.color.value, a.color is Color.GREEN, Color.RED in a.seen, Color.GREEN in a.seen)
a.kind = 5
a.color = Color.RED
a.seen.add(a.color)
print(a.kind, b.kind, a.color, b.color, len(a.seen), len(b.seen))
