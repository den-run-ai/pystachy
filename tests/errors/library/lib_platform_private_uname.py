# error: name '__pys_uname' is not defined
# lib/platform.py's private builtin is not a name of a program's own module named platform,
# as it is not of any other module: CPython raises NameError where the call runs.
import platform

print(platform.kernel())
