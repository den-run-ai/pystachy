# (tests/programs/reflection/annotation_cycle.py) annotations that read annot_cyc.Later, which
# annot_cyc has bound where it imports this module
from mods import annot_cyc as a


def make() -> a.Later:
    return a.Later()


class Holder:
    def __init__(self, item: a.Later) -> None:
        self.item = item


held: list[a.Later] = [make()]
print("bound:", len(held), Holder(held[0]).item is held[0])
