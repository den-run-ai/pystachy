# (tests/programs/reflection/annotation_cycle.py) a decorated def whose parameter's annotation
# reads annot_cyc.Later before annot_cyc binds it
import functools

import mods.annot_cyc as a


@functools.cache
def name(x: a.Later) -> str:
    return "later"


print("not reached")
