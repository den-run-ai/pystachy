# error: stublater.py:6: error: an @overload stub of 'f' must be followed by the def that implements it (calling a stub raises NotImplementedError)
# In an imported module as in the program, the def that replaces a stub must follow it past other
# defs only: code between them could call the stub.
import emods.stublater

print(emods.stublater.f(1))
