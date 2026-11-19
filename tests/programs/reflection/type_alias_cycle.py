# An assigned type alias's value is evaluated where the assignment runs: a class read through its
# module before that module's class statement has run, as during this circular import, raises
# AttributeError (whose message CPython words apart: tests/deviations/circular_attr.py)
try:
    import mods.talias_cyc_a
except AttributeError:
    print("AttributeError")
