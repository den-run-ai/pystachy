# (tests/programs/reflection/annotation_cycle.py) annotations that name annot_cyc.Later, which
# annot_cyc has not bound yet where it imports this module, where CPython does not evaluate them:
# in strings (forward references) and in a function's body
from mods import annot_cyc as a


def make(x: "a.Later | None", n: list["a.Later"]) -> "a.Later | None":
    return x


def count() -> int:
    held: list[a.Later] = []
    return len(held)


class Holder:
    item: "a.Later | None" = None


print("lazy:", make(None, []), count())
