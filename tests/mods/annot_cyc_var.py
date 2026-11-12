# (tests/programs/reflection/annotation_cycle.py) a module's annotated assignment whose
# annotation reads annot_cyc.Later before annot_cyc binds it, after the value
from mods import annot_cyc as a

print("value")
held: list[a.Later] = []
print("not reached")
