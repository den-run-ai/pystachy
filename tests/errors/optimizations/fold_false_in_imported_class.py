# error: fclass.py:6: error: class eload.fclass.C is not supported: its body holds statements other than fields, methods and a docstring; CPython runs this statement of the body of class C when module 'eload.fclass' is imported, and Pystachy does not check what a 'global' statement there runs
# The same in an imported module's class (eload/fclass.py, fold_false_in_class.py), which the
# program does not use: its body runs as the module's code does, and CPython prints 2.
import eload.fclass

print(eload.fclass.x)
