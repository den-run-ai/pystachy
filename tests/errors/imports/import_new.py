# error: import_new.py:6: error: class emods.new_class.Counted is not supported: the special method __new__ is not supported (CPython calls it to make each object of the class)
# A class of an imported module that defines __new__ is an error where the program uses it
# (CPython calls __new__ before __init__); the rest of the module compiles.
from emods.new_class import Counted, double
print(double(2))
print(Counted(3).n)
