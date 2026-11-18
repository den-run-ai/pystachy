# (tests/programs/reflection/annotation_cycle.py) a def whose annotations read annot_cyc.Later and
# annot_cyc.Other, which annot_cyc has not bound yet where it imports this module: CPython
# evaluates the parameters after the positional-only ones first
import mods.annot_cyc as a


def make(first: a.Later, /, n: a.Other) -> a.Later:
    return first


print("not reached")
