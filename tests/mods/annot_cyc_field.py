# (tests/programs/reflection/annotation_cycle.py) a class body's annotation that reads
# annot_cyc.Later before annot_cyc binds it
from mods import annot_cyc as a


class Holder:
    item: a.Later | None = None


print("not reached")
