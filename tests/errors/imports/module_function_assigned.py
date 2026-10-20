# error: module_function_assigned.py:11: error: 'emods.assigned_fn.greet' is bound both as a variable and as a function, class or import (not supported)
# A module's function is bound once: the program cannot assign another to it. The error is the
# assignment's, not the line of the statement compiled last
import emods.assigned_fn


def mine() -> str:
    return "mine"


emods.assigned_fn.greet = mine
print(emods.assigned_fn.greet())
