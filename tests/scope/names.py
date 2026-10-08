# What from scope.names import * takes: __all__ after += and append.
__all__ = ["visible", "total"]
__all__ += ["extra"]
__all__.append("helper")
visible = 1
total = len([1, 2, 3])
extra = "extra"
hidden = 2


def helper() -> str:
    return "names.helper"


def size(xs: list[int]) -> int:
    return len(xs)  # the builtin, though the main program defines a len of its own


def lazy() -> str:
    from scope.parse import parse  # binds parse in this function only

    return "+".join(parse("p,q"))


def parse() -> str:
    return "names.parse"
