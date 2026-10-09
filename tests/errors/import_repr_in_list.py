# error: import_repr_in_list.py:6: error: __repr__ must return str
# Printing a list of Shown objects calls Shown.__repr__, which has no return annotation (so
# returns None for Pystachy): an error where the program prints them, not at the class, and
# not where the objects are only made.
import emods.special
print(emods.special.Shown(1).x, [emods.special.Shown(2)])
