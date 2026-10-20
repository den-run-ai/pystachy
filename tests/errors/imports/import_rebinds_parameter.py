# error: import_rebinds_parameter.py:4: error: 'sep' is bound both as a variable and by an import (not supported)
# The import rebinds the parameter: CPython returns os.sep, "/", whatever the argument.
def separator(sep: str) -> str:
    from os import sep
    return sep


print(separator("\\"))
