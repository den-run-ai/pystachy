# error: unsupported call object()
# The compiler loads object()'s class for a program one of whose modules calls the name object: a
# program that calls it only by a name that an import binds to it is rejected, as on main. It works
# where any of the program's modules calls object() (docs/language/semantics.md#sentinels).
from builtins import object as obj

x = obj()
print(x is x)
