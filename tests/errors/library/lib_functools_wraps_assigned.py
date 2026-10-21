# error: lib_functools_wraps_assigned.py:7: error: wraps()'s assigned is supported as a tuple of str constants, or a module's name that one assignment binds to one (WRAPPER_ASSIGNMENTS): the attributes it names are known as Pystachy compiles
# a parameter's tuple, which the program gives as it runs
from functools import wraps


def d(f, names):
    @wraps(f, names)
    def w():
        pass
    return w


d(len, ("__name__",))
