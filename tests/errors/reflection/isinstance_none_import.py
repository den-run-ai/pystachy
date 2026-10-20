# error: isinstance_none_import.py:7: error: 'x' is bound both as a variable and by an import (not supported)
# The import rebinds x on the loop's second pass: CPython prints True, then False.
def f() -> None:
    x = None
    for i in range(2):
        print(isinstance(x, type(None)))
        import sys as x


f()
