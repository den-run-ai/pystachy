# Class attributes typed by another class's class attributes: alone, and as the keys, values and
# items of displays (mypyc's pretty-printer keys a table by Branch's constants).
from enum import Enum


class Mode(Enum):
    FAST = "f"
    SAFE = "s"


class Branch:
    BOOL = 100
    IS_ERROR = 101
    PREFIX = "is_"
    ALIASES = ["b", "e"]


class Failure(Exception):
    CODE = 7


class Printer:
    DEFAULT = Branch.BOOL
    PREFIX = Branch.PREFIX
    ALIASES = Branch.ALIASES
    CODE = Failure.CODE
    MODE = Mode.SAFE
    MODES = [Mode.FAST, Mode.SAFE]
    branch_op_names = {Branch.BOOL: ("%r", "bool"), Branch.IS_ERROR: ("is_error(%r)", "")}
    KINDS = {Branch.BOOL, Branch.IS_ERROR}
    BY_NAME = {"bool": Branch.BOOL}

    def show(self, kind: int) -> str:
        fmt, typ = self.branch_op_names[kind]
        return fmt + ":" + typ


p = Printer()
print(Printer.DEFAULT, p.PREFIX, Printer.CODE, p.show(Branch.BOOL), p.show(101), sorted(Printer.KINDS), Printer.BY_NAME["bool"])
print(Printer.MODE, p.MODE is Mode.SAFE, Printer.MODES, Printer.ALIASES is Branch.ALIASES)
Branch.ALIASES.append("x")
print(p.ALIASES, 100 in p.KINDS, 5 in Printer.KINDS)
