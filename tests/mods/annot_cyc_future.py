# (tests/programs/reflection/annotation_cycle.py) annotations that read annot_cyc.Later before
# annot_cyc binds it, in a module that imports annotations from __future__: CPython does not
# evaluate them
from __future__ import annotations

from mods import annot_cyc as a


def make(n: int) -> a.Later | None:
    return None


class Holder:
    item: a.Later | None = None


held: list[a.Later] = []
print("future:", make(1), len(held))
