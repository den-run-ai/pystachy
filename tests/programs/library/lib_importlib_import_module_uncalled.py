# A module that imports import_module and calls it with a computed name in a function the
# program does not call: the module compiles, as the functions of a library that load plugins
# by name do not stop a program that uses the rest of it.
import impmod_plug.alpha
import impmod_lazy

print(impmod_lazy.VALUE, impmod_lazy.static_backend())
