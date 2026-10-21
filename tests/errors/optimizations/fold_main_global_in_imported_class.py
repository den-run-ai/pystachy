# error: mainglobal.py:6: error: class eload.mainglobal.C is not supported: its body holds statements other than fields, methods and a docstring; CPython runs this statement of the body of class C when module 'eload.mainglobal' is imported, and Pystachy does not check what a 'global' statement there runs
# In an imported module, __name__ == "__main__" is decided at compile time, and a global statement
# in the branch it drops from a class body holds there too (fold_typing_global_in_class.py): the
# class body runs when the module is imported, though the program does not use the class, and
# CPython prints 2.
import eload.mainglobal

print(eload.mainglobal.x)
