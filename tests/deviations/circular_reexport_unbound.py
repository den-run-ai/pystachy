# Documented deviation (as circular_attr.py): a module's copy of another module's constant (from m
# import K), read through its module before the import that binds it has run (here because of a
# circular import), raises AttributeError, but its message does not say that the module is
# partially initialized, as CPython's does: partially initialized module 'circ.reexp_a' from
# '/path/to/circ/reexp_a.py' has no attribute 'K' (most likely due to a circular import)
try:
    from circ import reexp_a

    print(reexp_a.K)
except AttributeError as e:
    print(type(e).__name__, "partially initialized" in str(e), "has no attribute 'K'" in str(e))
