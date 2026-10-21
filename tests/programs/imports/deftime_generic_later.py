# A generic class that Pystachy leaves uncompiled reads a variable that is unbound when the class
# statement runs: NameError then, as in CPython
print("main: start")
import defmods.generic_later

print("main: not reached")
