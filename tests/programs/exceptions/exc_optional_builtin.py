# An optional import of a name that Pystachy's builtin module lacks runs its handler, as for a module.
have = True
try:
    from math import sqrt, cbrt_nonexistent
except ImportError:
    have = False
print(have, sqrt(4.0))
try:
    from os.path import exists, nothing_here
except ImportError:
    print("fallback", exists("/"))
try:
    from math import floor
except ImportError:
    print("no")
print("ok", floor(2.5))
