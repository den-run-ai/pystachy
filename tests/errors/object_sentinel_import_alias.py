# error: unsupported call object()
# The compiler loads object()'s class where a module calls the name object: a module that calls it
# only by a name that an import binds to it is rejected, as on main. It works where the module also
# calls object().
from builtins import object as obj

x = obj()
print(x is x)
