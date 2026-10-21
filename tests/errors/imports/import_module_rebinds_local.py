# error: import_module_rebinds_local.py:6: error: 'x' is bound both as a variable and by an import (not supported)
# The import rebinds x to the module sys: CPython prints <module 'sys' (built-in)>, where every
# read of x would read the variable.
def f() -> None:
    x = 1
    import sys as x
    print(x)


f()
