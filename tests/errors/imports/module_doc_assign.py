# error: assigning the __doc__ of module 'emods.empty' is not supported
# A module's __doc__ can be read, so an assignment of it from another module's top level is an
# error, not dropped as a function's or class's (f.__doc__ = ...) is
from emods import empty

empty.__doc__ = "replaced"
print(empty.__doc__)
