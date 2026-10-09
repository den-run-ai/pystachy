# error: import_overload_stub.py:6: error: an @overload stub of 'pick' must be followed by the def that implements it (calling a stub raises NotImplementedError)
# An imported module's stub that no def follows is an error only where the program calls it.
from emods.stubs import other, pick

print(other(1))
print(pick(2))
