# An optional from-import of a package: CPython imports each name the package does not bind as
# its submodule, in order (one that is not found is passed over), then binds the names. A
# submodule whose code raises ImportError stops the import before any name is bound; a name that
# is neither bound nor a submodule fails to bind. Either way the handler runs, also for a
# relative import (from . import _speedups in the package's own code).
try:
    from loader.fl import broken
except ImportError:
    print("fallback")
import loader.fl.user

print(loader.fl.X)
try:
    from loader.fl import one, nothere, two
except ImportError:
    print("no nothere")
print(one.V)
try:
    from loader.fl import X, two, broken, one
except ImportError:
    print("broken again")
try:
    from loader.fl import nothere2
except ImportError:
    print("no nothere2")
