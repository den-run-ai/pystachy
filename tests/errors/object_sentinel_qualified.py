# error: unsupported call object()
# The compiler loads object()'s class for a program one of whose modules calls the name object: a
# program that calls it only through the builtins module is rejected, as on main. It works where
# any of the program's modules calls object() (docs/language/semantics.md#sentinels).
import builtins

x = builtins.object()
print(x is x)
