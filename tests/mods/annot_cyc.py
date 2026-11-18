# (tests/programs/reflection/annotation_cycle.py) imports modules whose annotations read Later and
# Other through this module, before its class statements and after


def missing(e: AttributeError) -> str:
    # the attribute that e says this module lacks (CPython's message also says that the module is
    # partially initialized and names its file: tests/deviations/circular_attr.py)
    return str(e).split("attribute '")[1].split("'")[0]


try:
    import mods.annot_cyc_def
except AttributeError as e:
    print("def:", missing(e))
try:
    import mods.annot_cyc_deco
except AttributeError as e:
    print("decorated def:", missing(e))
try:
    import mods.annot_cyc_method
except AttributeError as e:
    print("method:", missing(e))
try:
    import mods.annot_cyc_field
except AttributeError as e:
    print("class body:", missing(e))
try:
    import mods.annot_cyc_var
except AttributeError as e:
    print("annotated assignment:", missing(e))
import mods.annot_cyc_lazy
import mods.annot_cyc_future


class Later:
    pass


class Other:
    pass


import mods.annot_cyc_bound
