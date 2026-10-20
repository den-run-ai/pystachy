# In an imported module, a class that defines a special method Pystachy never calls (__new__,
# __getattr__, __getattribute__, __setattr__, __delattr__, by a def or a class attribute, also
# through its base) is an error only where the program uses it: a program that imports the module
# without using the class compiles, and the class body runs when the module is imported.
# A class that defines __init_subclass__ is an error only where a class derives from it (CPython
# calls it then), also in the main program.
import defmods.uncalled as u
from defmods.uncalled import Counted, Hook


class Local(Exception):
    def __init_subclass__(cls) -> None:
        print("a subclass of Local")


print(u.double(21))
try:
    raise Local("raised")
except Local as e:
    print(e)
try:
    raise Hook("hooked")
except Exception as e:
    print(e)
