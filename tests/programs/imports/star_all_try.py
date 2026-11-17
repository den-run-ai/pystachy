# A star import takes the __all__ that a module's top-level try statement binds (#1513): the
# assignment that leads its body cannot raise, so CPython binds __all__ wherever the try runs,
# and only "a" is imported; main's own b stays.
b = "main's b"
from loader.alltry import *

print(a, b)
