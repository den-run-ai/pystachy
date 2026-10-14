# error: super_other.py:11: error: super() is only supported without arguments in a method of a class with a supported base (super(C, self) in a method of C is super())
from emods.super_other import B

print(B("x"))
