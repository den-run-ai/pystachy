# NewType("N", T) evaluates T where it runs: a class read through its module before that module's
# class statement has run, as during this circular import, raises AttributeError (whose message
# CPython words apart: tests/deviations/circular_attr.py)
try:
    import mods.newtype_cyc_a
except AttributeError:
    print("AttributeError")
