# A class body Pystachy leaves uncompiled reads a variable that is unbound when the module is
# imported: NameError then, as in CPython
print("main: start")
import defmods.unbound

print("main: not reached")
