# error: import_field_subclass.py:6: error: class emods.anns.Owner is not supported: class emods.anns.Derived is not supported: class inheritance is not supported
# A field set from a constructor of a class Pystachy cannot compile (a subclass) makes its class
# an error where it is used, with that class's reason (an annotation would not help).
from emods.anns import Owner

print(Owner().n)
