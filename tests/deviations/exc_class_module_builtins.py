# Documented deviation (docs/language/compatibility.md): an exception class's __module__ = "builtins"
# raises NotImplementedError, and the class keeps its module. CPython assigns it, and prints
# builtins, its uncaught exceptions' line then naming the class alone.
class E(Exception):
    pass


try:
    E.__module__ = "builtins"
except NotImplementedError as e:
    print("NotImplementedError:", e)
print(E.__module__)
