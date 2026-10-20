# error: import_rebinds_local.py:6: error: 'pi' is bound both as a variable and by an import (not supported)
# A function binds a name once, as module code does: CPython's import rebinds the variable pi
# (area() returns 3.141592653589793), where every read of pi would read the variable.
def area(r: float) -> float:
    pi = 3.0
    from math import pi
    return pi * r * r


print(area(1.0))
