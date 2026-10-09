# An except clause may name a builtin exception class as an attribute of the builtins module, and
# os.error, which is OSError.
import builtins
import os
try:
    int("x")
except builtins.ValueError as e:
    print("caught", e)
try:
    os.remove("/nonexistent_zz")
except (builtins.KeyError, os.error) as e:
    print("caught", repr(e))
