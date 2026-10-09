# error: import_overload_stub_static.py:6: error: an @overload stub of 'make' must be followed by the def that implements it (calling a stub raises NotImplementedError)
# An imported class's stub of a static method, called through the class (CPython's stub raises
# NotImplementedError however it is called).
from emods.stubs import Pair

print(Pair.make(2))
