# error: unsupported module attribute os.__file__
# A module compiled from source has a __file__; os, which the compiler provides, has none
import os

print(os.path.realpath(os.__file__))
