# (tests/programs/reflection/annotation_cycle.py) a method whose parameter's annotation reads
# annot_cyc.Later before annot_cyc binds it, which CPython evaluates where the class statement runs
from mods import annot_cyc as a


class Holder:
    def put(self, x: a.Later | None) -> None:
        pass


print("not reached")
