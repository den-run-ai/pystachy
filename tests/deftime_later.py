# A default value that Pystachy cannot compile reads a variable that is unbound when the def
# statement runs: NameError then, as in CPython
print("main: start")
import defmods.later

print("main: not reached")
