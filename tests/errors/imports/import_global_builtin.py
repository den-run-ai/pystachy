# error: import_global_builtin.py:8: error: an import of 'sys' in a function that declares it global is not supported
# The import rebinds the module's sys to os where the function runs.
import sys


def setup() -> None:
    global sys
    import os as sys


setup()
if sys.platform == "win32":
    print("win")
else:
    print("posix")
