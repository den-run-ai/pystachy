# Helper of tests/programs/inference/class_attr_class_const_module.py: an imported module
# whose class bodies and defaults read other classes' attributes.
from enum import Enum


class Mode(Enum):
    FAST = "f"
    SAFE = "s"


class Branch:
    BOOL = 100
    IS_ERROR = 101
    LABELS = ["bool", "is_error"]


class Printer:
    DEFAULT = Branch.BOOL
    MODE = Mode.SAFE
    MODES = [Mode.FAST, Mode.SAFE]
    LABELS = Branch.LABELS
    branch_op_names = {Branch.BOOL: ("%r", "bool"), Branch.IS_ERROR: ("is_error(%r)", "")}
    KINDS = {Branch.BOOL, Branch.IS_ERROR}
    PAIR = (Branch.IS_ERROR, Mode.FAST)
    limit: int = Branch.IS_ERROR

    def __init__(self, traceback: bool = False) -> None:
        self.kind = Branch.IS_ERROR if traceback else Branch.BOOL
        self.mode = Mode.FAST
        self.seen = {Mode.SAFE}

    def show(self, kind: int = Branch.BOOL, mode: Mode = Mode.SAFE) -> str:
        fmt, typ = self.branch_op_names[kind]
        return fmt + ":" + typ + ":" + mode.name


def describe(kind: int = Branch.IS_ERROR, modes=(Mode.FAST, Mode.SAFE)) -> str:
    return str(kind) + "/" + "".join([m.value for m in modes])


class Unused:
    # CPython makes these when it imports the module; the program reads none of them, and
    # their items or annotations have other types than their first items or values
    MIXED = {1, "a"}
    TABLE = {Branch.BOOL: "bool", "error": Branch.IS_ERROR}
    LABEL: str = Branch.BOOL
