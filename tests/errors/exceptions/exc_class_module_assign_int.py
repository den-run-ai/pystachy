# error: exc_class_module_assign_int.py:8: error: assigning int to E.__module__ is not supported: assign a str
# CPython takes any object for a class's __module__ (an uncaught exception's line then names the
# module <unknown>); Pystachy's exception class names a module by a str
class E(Exception):
    pass


E.__module__ = 5
