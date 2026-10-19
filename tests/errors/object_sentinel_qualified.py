# error: unsupported call object()
# The compiler loads object()'s class where a module calls the name object: a module that calls it
# only through the builtins module is rejected, as on main. It works where the module also calls
# object().
import builtins

x = builtins.object()
print(x is x)
