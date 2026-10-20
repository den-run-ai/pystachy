# error: import_overload_stub_method.py:7: error: an @overload stub of 'scaled' must be followed by the def that implements it (calling a stub raises NotImplementedError)
# An imported class's stub method that no def follows is an error only where the program calls
# it: the class compiles.
from emods.stubs import Pair

print(Pair(1, 2).total())
print(Pair(1, 2).scaled(2))
