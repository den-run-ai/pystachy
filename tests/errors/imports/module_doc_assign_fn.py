# error: assigning the __doc__ of module 'emods.empty' is not supported
# (in a function: the module's __doc__ is its docstring or None, a constant while its own code
# binds no __doc__)
import emods.empty


def retitle() -> None:
    emods.empty.__doc__ = "replaced"


retitle()
