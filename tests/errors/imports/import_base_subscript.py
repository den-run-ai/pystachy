# error: emods/base_subscript.py:5: error: type 'Plain' is not subscriptable (CPython evaluates the bases of class Sub when module 'emods.base_subscript' is imported)
# An imported module's class statement runs, used or not, and evaluates its bases: Plain[int], of
# a class that cannot be subscripted, fails the import.
import emods.base_subscript

print(emods.base_subscript.g())
